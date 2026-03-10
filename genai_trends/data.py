from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from time import perf_counter, sleep
from typing import Any, Iterable
from urllib.parse import quote
import os
import re

import pandas as pd
import requests

from genai_trends.logging_utils import get_logger


MASTODON_DEFAULT_BASE_URL = "https://mastodon.social"
MASTODON_PAGE_SIZE = 40
MASTODON_MAX_PAGES = 5
MASTODON_TAG_TIMELINE_URL = "/api/v1/timelines/tag/{tag}"
GUARDIAN_SEARCH_URL = "https://content.guardianapis.com/search"
HACKER_NEWS_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
HACKER_NEWS_PAGE_SIZE = 100
HACKER_NEWS_MAX_PAGES = 10

REQUEST_TIMEOUT = (5, 30)
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


def _mastodon_base_url() -> str:
    configured = _required_env("MASTODON_BASE_URL")
    if configured:
        return configured.rstrip("/")
    return MASTODON_DEFAULT_BASE_URL


def _mastodon_headers() -> dict[str, str]:
    headers = {"User-Agent": "genai-trends-dashboard/0.1"}
    access_token = _required_env("MASTODON_ACCESS_TOKEN")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _hashtag_slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", term.lower())


def fetch_mastodon_series(
    session: requests.Session,
    term: str,
    period_start: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    hashtag = _hashtag_slug(term)
    if not hashtag:
        return _empty_series(period_index), _config_error_metric("mastodon", term, "empty hashtag slug")

    url = f"{_mastodon_base_url()}{MASTODON_TAG_TIMELINE_URL.format(tag=quote(hashtag))}"
    headers = _mastodon_headers()
    timestamps: list[pd.Timestamp] = []
    max_id: str | None = None
    total_rows = 0
    partial = False
    last_status_code: int | None = None

    try:
        for page in range(MASTODON_MAX_PAGES):
            params: dict[str, Any] = {"limit": MASTODON_PAGE_SIZE}
            if max_id:
                params["max_id"] = max_id

            response = _retryable_http_get(session, url, params, headers=headers)
            last_status_code = response.status_code
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("mastodon tag timeline did not return a list")
            if not payload:
                break

            total_rows += len(payload)
            oldest_timestamp: pd.Timestamp | None = None
            for status in payload:
                created_at = status.get("created_at")
                if not created_at:
                    continue
                timestamp = pd.to_datetime(created_at, utc=True)
                oldest_timestamp = timestamp if oldest_timestamp is None else min(oldest_timestamp, timestamp)
                if timestamp.date() >= period_start:
                    timestamps.append(timestamp)

            last_id = payload[-1].get("id")
            if not last_id:
                break
            max_id = str(last_id)

            if oldest_timestamp is not None and oldest_timestamp.date() < period_start:
                break
            if len(payload) < MASTODON_PAGE_SIZE:
                break
            if page == MASTODON_MAX_PAGES - 1:
                partial = True
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return _empty_series(period_index), _metric(
            "mastodon",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            detail=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric("mastodon", term, "request_error", started_at, detail=str(exc))
    except ValueError as exc:
        return _empty_series(period_index), _metric("mastodon", term, "parse_error", started_at, detail=str(exc))
    except Exception as exc:
        return _empty_series(period_index), _metric("mastodon", term, "error", started_at, detail=str(exc))

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), _metric(
        "mastodon",
        term,
        "ok",
        started_at,
        http_status=last_status_code,
        partial=partial,
        rows_returned=total_rows,
        detail=f"#{hashtag}",
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


def _hacker_news_date_filters(period_start: date, period_end: date) -> str:
    start_ts = int(pd.Timestamp(period_start).timestamp())
    end_ts = int((pd.Timestamp(period_end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)).timestamp())
    return f"created_at_i>={start_ts},created_at_i<={end_ts}"


def fetch_hacker_news_series(
    session: requests.Session,
    term: str,
    period_start: date,
    period_end: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    timestamps: list[pd.Timestamp] = []
    total_rows = 0
    partial = False
    last_status_code: int | None = None

    try:
        for page in range(HACKER_NEWS_MAX_PAGES):
            params = {
                "query": term,
                "tags": "story",
                "numericFilters": _hacker_news_date_filters(period_start, period_end),
                "hitsPerPage": HACKER_NEWS_PAGE_SIZE,
                "page": page,
            }
            response = _retryable_http_get(session, HACKER_NEWS_SEARCH_URL, params)
            last_status_code = response.status_code
            payload = response.json()
            hits = payload.get("hits", [])
            if not isinstance(hits, list):
                raise ValueError("hacker news search did not return hits")
            if not hits:
                break

            total_rows += len(hits)
            for hit in hits:
                created_at_i = hit.get("created_at_i")
                if created_at_i is None:
                    continue
                timestamp = pd.to_datetime(int(created_at_i), unit="s", utc=True)
                if period_start <= timestamp.date() <= period_end:
                    timestamps.append(timestamp)

            nb_pages = payload.get("nbPages", 0)
            if not isinstance(nb_pages, int):
                raise ValueError("hacker news search did not return integer nbPages")
            if page + 1 >= nb_pages:
                break
            if page == HACKER_NEWS_MAX_PAGES - 1:
                partial = True
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return _empty_series(period_index), _metric(
            "hacker_news",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            detail=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric(
            "hacker_news",
            term,
            "request_error",
            started_at,
            detail=str(exc),
        )
    except ValueError as exc:
        return _empty_series(period_index), _metric("hacker_news", term, "parse_error", started_at, detail=str(exc))
    except Exception as exc:
        return _empty_series(period_index), _metric("hacker_news", term, "error", started_at, detail=str(exc))

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), _metric(
        "hacker_news",
        term,
        "ok",
        started_at,
        http_status=last_status_code,
        partial=partial,
        rows_returned=total_rows,
    )


def _load_mastodon_source(
    session: requests.Session,
    unique_terms: list[str],
    period_start: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], dict[str, FetchMetric]]:
    series_map: dict[str, pd.Series] = {}
    metrics_map: dict[str, FetchMetric] = {}
    blocked = False

    for term in unique_terms:
        if blocked:
            metric = _metric("mastodon", term, "skipped", perf_counter(), detail="skipped after earlier access block")
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = metric
            continue

        series, metric = fetch_mastodon_series(session, term, period_start, granularity, period_index)
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


def _load_hacker_news_source(
    session: requests.Session,
    unique_terms: list[str],
    period_start: date,
    period_end: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], dict[str, FetchMetric]]:
    series_map: dict[str, pd.Series] = {}
    metrics_map: dict[str, FetchMetric] = {}
    rate_limited = False

    for term in unique_terms:
        if rate_limited:
            metric = _metric(
                "hacker_news",
                term,
                "skipped",
                perf_counter(),
                throttled=True,
                detail="skipped after earlier Hacker News rate limit",
            )
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = metric
            continue

        series, metric = fetch_hacker_news_series(
            session,
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

    social_series_map, social_metrics = _load_mastodon_source(
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
    trends_series_map, trends_metrics = _load_hacker_news_source(
        session,
        unique_terms,
        period_start,
        period_end,
        granularity,
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
