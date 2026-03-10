from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from time import perf_counter, sleep
from typing import Any, Iterable
import os

import pandas as pd
import requests

from genai_trends.logging_utils import get_logger


REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_SEARCH_URL = "https://oauth.reddit.com/search"
GUARDIAN_SEARCH_URL = "https://content.guardianapis.com/search"
SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"

REQUEST_TIMEOUT = (5, 30)
GOOGLE_TRENDS_BATCH_SIZE = 5
BACKOFF_DELAYS_SECONDS = (1.0, 2.0)
GUARDIAN_CALL_DELAY_SECONDS = 1.1

SOURCE_FIELD_MAP = {
    "social_media": "social_media",
    "news_mentions": "news_mentions",
    "google_trends": "google_trends",
}

SOURCE_WEIGHT_MAP = {
    "social_media": "social",
    "news_mentions": "news",
    "google_trends": "google_trends",
}

LOGGER = get_logger("genai_trends")
FETCH_LOGGER = get_logger("genai_trends.fetch")


@dataclass
class FetchMetric:
    source: str
    tracked_item: str
    status: str
    duration_ms: float
    http_status: int | None = None
    throttled: bool = False
    partial: bool = False
    rows_returned: int = 0
    detail: str = ""


@dataclass
class LoadStatus:
    total_duration_ms: float
    api_calls: int
    throttled_calls: int
    partial_calls: int
    error_calls: int
    partial_rows: int


def _metric(
    source: str,
    tracked_item: str,
    status: str,
    started_at: float,
    *,
    http_status: int | None = None,
    throttled: bool = False,
    partial: bool = False,
    rows_returned: int = 0,
    detail: str = "",
) -> FetchMetric:
    metric = FetchMetric(
        source=source,
        tracked_item=tracked_item,
        status=status,
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
        http_status=http_status,
        throttled=throttled,
        partial=partial,
        rows_returned=rows_returned,
        detail=detail,
    )
    FETCH_LOGGER.info("fetch_metric", extra={"event": "fetch_metric", **asdict(metric)})
    return metric


def _date_index(period_start: date, period_end: date, granularity: str) -> pd.DatetimeIndex:
    freq_map = {"daily": "D", "weekly": "W-MON", "monthly": "MS"}
    return pd.date_range(start=pd.Timestamp(period_start), end=pd.Timestamp(period_end), freq=freq_map[granularity])


def _item_records(tracked_items: dict) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for topic_key, topic_data in tracked_items["topics"].items():
        topic_name = topic_key.replace("_", " ")
        for item in topic_data["items"]:
            records.append({"topic": topic_name, "tracked_item": item})
    return records


def _unique_terms(item_records: list[dict[str, str]]) -> list[str]:
    return sorted({record["tracked_item"] for record in item_records})


def _empty_series(period_index: pd.DatetimeIndex, fill_value: float | None = None) -> pd.Series:
    return pd.Series([fill_value] * len(period_index), index=period_index, dtype="float64")


def _align_series(series: pd.Series, period_index: pd.DatetimeIndex, aggregation: str) -> pd.Series:
    if series.empty:
        return _empty_series(period_index, 0.0)

    working = series.copy()
    working.index = pd.to_datetime(working.index)
    working = working.sort_index()

    if aggregation == "sum":
        aligned = working.groupby(level=0).sum().reindex(period_index, fill_value=0.0)
    else:
        aligned = working.groupby(level=0).mean().reindex(period_index)
        aligned = aligned.interpolate(limit_direction="both").fillna(0.0)

    return aligned.astype("float64")


def _phrase_query(term: str) -> str:
    return f"\"{term}\"" if " " in term else term


def _bucket_series_from_timestamps(
    timestamps: Iterable[pd.Timestamp | str],
    period_index: pd.DatetimeIndex,
    granularity: str,
) -> pd.Series:
    timestamp_values = list(timestamps)
    if not timestamp_values:
        return _empty_series(period_index, 0.0)

    series = pd.Series(1.0, index=pd.to_datetime(timestamp_values, utc=True))
    series.index = series.index.tz_convert(None)
    freq_map = {"daily": "D", "weekly": "W-MON", "monthly": "MS"}
    bucketed = series.resample(freq_map[granularity]).sum()
    return _align_series(bucketed, period_index, "sum")


def _retryable_http_get(
    session: requests.Session,
    url: str,
    params: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt, delay in enumerate((0.0, *BACKOFF_DELAYS_SECONDS), start=1):
        if delay:
            sleep(delay)
        try:
            response = session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 429 and attempt <= len(BACKOFF_DELAYS_SECONDS):
                last_error = requests.HTTPError("429 throttled", response=response)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            response = getattr(exc, "response", None)
            if response is None or response.status_code != 429 or attempt > len(BACKOFF_DELAYS_SECONDS):
                break
    if last_error is None:
        raise RuntimeError("request failed without error details")
    raise last_error


def _required_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is not None:
        value = value.strip()
        if value:
            return value

    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
    except Exception:
        secret_value = None

    if isinstance(secret_value, str):
        secret_value = secret_value.strip()
        if secret_value:
            return secret_value

    return None


def _config_error_metric(source: str, tracked_item: str, detail: str) -> FetchMetric:
    return _metric(source, tracked_item, "config_error", perf_counter(), detail=detail)


def _build_reddit_user_agent() -> str:
    configured = _required_env("REDDIT_USER_AGENT")
    if configured:
        return configured
    return "genai-trends-dashboard/0.1"


def _get_reddit_access_token(session: requests.Session) -> str:
    client_id = _required_env("REDDIT_CLIENT_ID")
    client_secret = _required_env("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("missing REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET")

    response = session.post(
        REDDIT_TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": _build_reddit_user_agent()},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise ValueError("reddit token response did not include access_token")
    return token


def fetch_reddit_series(
    session: requests.Session,
    access_token: str,
    term: str,
    period_start: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    params = {
        "q": _phrase_query(term),
        "sort": "new",
        "limit": 100,
        "type": "link",
        "t": "week",
    }
    headers = {
        "Authorization": f"bearer {access_token}",
        "User-Agent": _build_reddit_user_agent(),
    }

    try:
        response = _retryable_http_get(session, REDDIT_SEARCH_URL, params, headers=headers)
        payload = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return _empty_series(period_index), _metric(
            "reddit",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            detail=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric("reddit", term, "request_error", started_at, detail=str(exc))
    except Exception as exc:
        return _empty_series(period_index), _metric("reddit", term, "error", started_at, detail=str(exc))

    children = payload.get("data", {}).get("children", [])
    timestamps: list[pd.Timestamp] = []
    for child in children:
        created_utc = child.get("data", {}).get("created_utc")
        if created_utc is None:
            continue
        timestamp = pd.to_datetime(created_utc, unit="s", utc=True)
        if timestamp.date() >= period_start:
            timestamps.append(timestamp)

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), _metric(
        "reddit",
        term,
        "ok",
        started_at,
        http_status=response.status_code,
        rows_returned=len(children),
    )


def fetch_guardian_series(
    session: requests.Session,
    api_key: str,
    term: str,
    period_start: date,
    period_end: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    params = {
        "api-key": api_key,
        "q": _phrase_query(term),
        "from-date": period_start.isoformat(),
        "to-date": period_end.isoformat(),
        "page-size": 200,
        "order-by": "newest",
    }

    try:
        response = _retryable_http_get(session, GUARDIAN_SEARCH_URL, params)
        payload = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return _empty_series(period_index), _metric(
            "guardian",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            detail=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric("guardian", term, "request_error", started_at, detail=str(exc))
    except ValueError as exc:
        return _empty_series(period_index), _metric("guardian", term, "parse_error", started_at, detail=str(exc))
    except Exception as exc:
        return _empty_series(period_index), _metric("guardian", term, "error", started_at, detail=str(exc))

    results = payload.get("response", {}).get("results", [])
    timestamps = [item.get("webPublicationDate") for item in results if item.get("webPublicationDate")]

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), _metric(
        "guardian",
        term,
        "ok",
        started_at,
        http_status=response.status_code,
        rows_returned=len(results),
    )


def _serpapi_date_value(period_start: date, period_end: date) -> str:
    if (period_end - period_start).days <= 6:
        return "now 7-d"
    return f"{period_start.isoformat()} {period_end.isoformat()}"


def _extract_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("<", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def fetch_serpapi_google_trends_batch(
    session: requests.Session,
    terms: list[str],
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], list[FetchMetric], bool]:
    started_at = perf_counter()
    api_key = _required_env("SERPAPI_API_KEY")
    if not api_key:
        detail = "missing SERPAPI_API_KEY"
        metrics = [_config_error_metric("serpapi", term, detail) for term in terms]
        return {term: _empty_series(period_index) for term in terms}, metrics, False

    params = {
        "engine": "google_trends",
        "data_type": "TIMESERIES",
        "q": ",".join(terms),
        "date": _serpapi_date_value(period_start, period_end),
        "tz": "0",
        "api_key": api_key,
    }

    try:
        response = _retryable_http_get(session, SERPAPI_SEARCH_URL, params)
        payload = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        throttled = status_code == 429
        metrics = [
            _metric(
                "serpapi",
                term,
                "http_error",
                started_at,
                http_status=status_code,
                throttled=throttled,
                detail=str(exc),
            )
            for term in terms
        ]
        return {term: _empty_series(period_index) for term in terms}, metrics, throttled
    except requests.RequestException as exc:
        metrics = [_metric("serpapi", term, "request_error", started_at, detail=str(exc)) for term in terms]
        return {term: _empty_series(period_index) for term in terms}, metrics, False
    except ValueError as exc:
        metrics = [_metric("serpapi", term, "parse_error", started_at, detail=str(exc)) for term in terms]
        return {term: _empty_series(period_index) for term in terms}, metrics, False

    api_error = payload.get("error")
    if api_error:
        detail = str(api_error)
        throttled = "429" in detail or "Too Many Requests" in detail
        metrics = [
            _metric("serpapi", term, "error", started_at, throttled=throttled, detail=detail)
            for term in terms
        ]
        return {term: _empty_series(period_index) for term in terms}, metrics, throttled

    timeline = payload.get("interest_over_time", {}).get("timeline_data", [])
    if not timeline:
        metrics = [_metric("serpapi", term, "ok", started_at, rows_returned=0) for term in terms]
        return {term: _empty_series(period_index, 0.0) for term in terms}, metrics, False

    raw_points: dict[str, list[tuple[pd.Timestamp, float]]] = {term: [] for term in terms}
    for item in timeline:
        timestamp_raw = item.get("timestamp")
        if timestamp_raw is None:
            continue
        try:
            timestamp = pd.to_datetime(int(timestamp_raw), unit="s", utc=True).tz_convert(None)
        except Exception:
            continue

        values = item.get("values", [])
        for index, term in enumerate(terms):
            if index >= len(values):
                continue
            value_entry = values[index]
            numeric_value = _extract_numeric_value(value_entry.get("extracted_value"))
            if numeric_value is None:
                numeric_value = _extract_numeric_value(value_entry.get("value"))
            if numeric_value is None:
                continue
            raw_points[term].append((timestamp, numeric_value))

    series_map: dict[str, pd.Series] = {}
    metrics: list[FetchMetric] = []
    for term in terms:
        points = raw_points[term]
        if not points:
            series_map[term] = _empty_series(period_index, 0.0)
            metrics.append(_metric("serpapi", term, "ok", started_at, rows_returned=0))
            continue

        dates = [point[0] for point in points]
        values = [point[1] for point in points]
        series = pd.Series(values, index=pd.to_datetime(dates))
        series_map[term] = _align_series(series, period_index, "mean")
        metrics.append(_metric("serpapi", term, "ok", started_at, rows_returned=len(points)))

    return series_map, metrics, False


def _load_reddit_source(
    session: requests.Session,
    unique_terms: list[str],
    period_start: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], dict[str, FetchMetric]]:
    series_map: dict[str, pd.Series] = {}
    metrics_map: dict[str, FetchMetric] = {}
    access_token: str | None = None

    try:
        access_token = _get_reddit_access_token(session)
    except Exception as exc:
        detail = str(exc)
        for term in unique_terms:
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = _config_error_metric("reddit", term, detail)
        return series_map, metrics_map

    blocked = False
    for term in unique_terms:
        if blocked:
            metric = _metric("reddit", term, "skipped", perf_counter(), detail="skipped after earlier access block")
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = metric
            continue

        series, metric = fetch_reddit_series(session, access_token, term, period_start, granularity, period_index)
        if metric.http_status in {401, 403}:
            blocked = True
        series_map[term] = series
        metrics_map[term] = metric

    return series_map, metrics_map


def _load_guardian_source(
    session: requests.Session,
    unique_terms: list[str],
    period_start: date,
    period_end: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], dict[str, FetchMetric]]:
    series_map: dict[str, pd.Series] = {}
    metrics_map: dict[str, FetchMetric] = {}
    api_key = _required_env("GUARDIAN_API_KEY")
    if not api_key:
        detail = "missing GUARDIAN_API_KEY"
        for term in unique_terms:
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = _config_error_metric("guardian", term, detail)
        return series_map, metrics_map

    rate_limited = False
    for index, term in enumerate(unique_terms):
        if rate_limited:
            metric = _metric(
                "guardian",
                term,
                "skipped",
                perf_counter(),
                throttled=True,
                detail="skipped after earlier Guardian rate limit",
            )
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = metric
            continue

        if index > 0:
            sleep(GUARDIAN_CALL_DELAY_SECONDS)

        series, metric = fetch_guardian_series(
            session,
            api_key,
            term,
            period_start,
            period_end,
            granularity,
            period_index,
        )
        if metric.throttled:
            rate_limited = True
        series_map[term] = series
        metrics_map[term] = metric

    return series_map, metrics_map


def _load_serpapi_google_trends_source(
    session: requests.Session,
    unique_terms: list[str],
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], dict[str, FetchMetric]]:
    series_map: dict[str, pd.Series] = {}
    metrics_map: dict[str, FetchMetric] = {}
    rate_limited = False

    for index in range(0, len(unique_terms), GOOGLE_TRENDS_BATCH_SIZE):
        batch = unique_terms[index : index + GOOGLE_TRENDS_BATCH_SIZE]
        if rate_limited:
            for term in batch:
                metric = _metric(
                    "serpapi",
                    term,
                    "skipped",
                    perf_counter(),
                    throttled=True,
                    detail="skipped after earlier SerpApi rate limit",
                )
                series_map[term] = _empty_series(period_index)
                metrics_map[term] = metric
            continue

        batch_series_map, batch_metrics, throttled = fetch_serpapi_google_trends_batch(
            session,
            batch,
            period_start,
            period_end,
            period_index,
        )
        rate_limited = throttled
        for term in batch:
            series_map[term] = batch_series_map[term]
        for metric in batch_metrics:
            metrics_map[metric.tracked_item] = metric

    return series_map, metrics_map


def _build_status(metrics: list[FetchMetric], dataset: pd.DataFrame, total_duration_ms: float) -> LoadStatus:
    return LoadStatus(
        total_duration_ms=round(total_duration_ms, 1),
        api_calls=len(metrics),
        throttled_calls=sum(1 for metric in metrics if metric.throttled),
        partial_calls=sum(1 for metric in metrics if metric.partial),
        error_calls=sum(1 for metric in metrics if metric.status not in {"ok", "skipped"}),
        partial_rows=int(dataset["partial_data_warning"].sum()) if not dataset.empty else 0,
    )


def generate_dataset(
    context: dict,
    tracked_items: dict,
    period_start: date,
    period_end: date,
    granularity: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    total_started_at = perf_counter()
    period_index = _date_index(period_start, period_end, granularity)
    item_records = _item_records(tracked_items)
    unique_terms = _unique_terms(item_records)
    weights = context["metrics"]["composite_score"]["factors"]
    selected_sources = context["data_sources"]["selected"]

    LOGGER.info(
        "dataset_load_started",
        extra={
            "event": "dataset_load_started",
            "tracked_item_count": len(unique_terms),
            "granularity": granularity,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "social_provider": selected_sources["social_media"],
            "news_provider": selected_sources["news_mentions"],
            "trends_provider": selected_sources["google_trends"],
        },
    )

    session = requests.Session()
    session.headers.update({"User-Agent": "genai-trends-dashboard/0.1"})

    social_series_map, social_metrics = _load_reddit_source(
        session,
        unique_terms,
        period_start,
        granularity,
        period_index,
    )
    news_series_map, news_metrics = _load_guardian_source(
        session,
        unique_terms,
        period_start,
        period_end,
        granularity,
        period_index,
    )
    trends_series_map, trends_metrics = _load_serpapi_google_trends_source(
        session,
        unique_terms,
        period_start,
        period_end,
        period_index,
    )
    session.close()

    rows: list[dict[str, Any]] = []
    for record in item_records:
        topic = record["topic"]
        tracked_item = record["tracked_item"]
        source_series = {
            "social_media": social_series_map[tracked_item],
            "news_mentions": news_series_map[tracked_item],
            "google_trends": trends_series_map[tracked_item],
        }
        source_metrics = {
            "social_media": social_metrics[tracked_item],
            "news_mentions": news_metrics[tracked_item],
            "google_trends": trends_metrics[tracked_item],
        }

        for bucket in period_index:
            row = {
                "topic": topic,
                "tracked_item": tracked_item,
                "time_granularity": granularity,
                "period_start": bucket.date().isoformat(),
                "period_end": bucket.date().isoformat(),
            }

            available_sources: list[str] = []
            partial_data_warning = False
            composite_score = 0.0

            for source_key, field_name in SOURCE_FIELD_MAP.items():
                value = source_series[source_key].get(bucket)
                source_metric = source_metrics[source_key]
                if pd.isna(value):
                    row[f"{field_name}_frequency"] = None
                    partial_data_warning = True
                    continue

                numeric_value = round(float(value), 2)
                row[f"{field_name}_frequency"] = numeric_value
                available_sources.append(selected_sources[source_key])
                composite_score += numeric_value * weights[SOURCE_WEIGHT_MAP[source_key]]
                partial_data_warning = partial_data_warning or source_metric.partial

            row["available_sources"] = ", ".join(available_sources)
            row["partial_data_warning"] = partial_data_warning or len(available_sources) < len(SOURCE_FIELD_MAP)
            row["composite_score"] = round(composite_score, 2)
            rows.append(row)

    dataset = pd.DataFrame(rows)
    metrics = list(social_metrics.values()) + list(news_metrics.values()) + list(trends_metrics.values())
    total_duration_ms = (perf_counter() - total_started_at) * 1000
    status = _build_status(metrics, dataset, total_duration_ms)

    LOGGER.info("dataset_load_finished", extra={"event": "dataset_load_finished", **asdict(status)})

    return dataset, asdict(status)


def build_topic_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.groupby(["period_end", "topic"], as_index=False)["composite_score"].mean().sort_values("period_end")


def build_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "topic",
        "tracked_item",
        "time_granularity",
        "period_start",
        "period_end",
        "social_media_frequency",
        "news_mentions_frequency",
        "google_trends_frequency",
        "composite_score",
        "available_sources",
        "partial_data_warning",
    ]
    return frame[columns].sort_values(["period_end", "tracked_item"]).reset_index(drop=True)
