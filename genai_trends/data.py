from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from time import perf_counter, sleep
from typing import Any, Iterable

import pandas as pd
import requests
from pytrends.request import TrendReq

from genai_trends.logging_utils import get_logger


BLUESKY_SEARCH_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUEST_TIMEOUT = (5, 30)
GOOGLE_TRENDS_BATCH_SIZE = 5
BACKOFF_DELAYS_SECONDS = (1.0, 2.0)

SOURCE_NAME_MAP = {
    "social_media": "bluesky",
    "news_mentions": "gdelt",
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
    FETCH_LOGGER.info(
        "fetch_metric",
        extra={"event": "fetch_metric", **asdict(metric)},
    )
    return metric


def _date_index(period_start: date, period_end: date, granularity: str) -> pd.DatetimeIndex:
    freq_map = {"daily": "D", "weekly": "W-MON", "monthly": "MS"}
    start = pd.Timestamp(period_start)
    end = pd.Timestamp(period_end)
    return pd.date_range(start=start, end=end, freq=freq_map[granularity])


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


def _align_series(
    series: pd.Series,
    period_index: pd.DatetimeIndex,
    aggregation: str,
) -> pd.Series:
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
    timestamps: Iterable[str],
    period_index: pd.DatetimeIndex,
    granularity: str,
) -> pd.Series:
    timestamps = list(timestamps)
    if not timestamps:
        return _empty_series(period_index, 0.0)

    series = pd.Series(1.0, index=pd.to_datetime(timestamps, utc=True))
    series.index = series.index.tz_convert(None)
    freq_map = {"daily": "D", "weekly": "W-MON", "monthly": "MS"}
    bucketed = series.resample(freq_map[granularity]).sum()
    return _align_series(bucketed, period_index, "sum")


def _retryable_http_get(
    session: requests.Session,
    url: str,
    params: dict[str, Any],
) -> requests.Response:
    last_error: Exception | None = None
    for attempt, delay in enumerate((0.0, *BACKOFF_DELAYS_SECONDS), start=1):
        if delay:
            sleep(delay)
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
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


def fetch_bluesky_series(
    session: requests.Session,
    term: str,
    period_start: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    params = {"q": _phrase_query(term), "sort": "latest", "limit": 100}

    try:
        response = _retryable_http_get(session, BLUESKY_SEARCH_URL, params)
        payload = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return _empty_series(period_index), _metric(
            "bluesky",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            detail=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric(
            "bluesky",
            term,
            "request_error",
            started_at,
            detail=str(exc),
        )
    except Exception as exc:
        return _empty_series(period_index), _metric(
            "bluesky",
            term,
            "error",
            started_at,
            detail=str(exc),
        )

    posts = payload.get("posts", [])
    timestamps = []
    for post in posts:
        record = post.get("record", {})
        created_at = record.get("createdAt") or post.get("indexedAt")
        if created_at and pd.to_datetime(created_at).date() >= period_start:
            timestamps.append(created_at)

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), _metric(
        "bluesky",
        term,
        "ok",
        started_at,
        http_status=response.status_code,
        rows_returned=len(posts),
    )


def fetch_gdelt_series(
    session: requests.Session,
    term: str,
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    params = {
        "query": _phrase_query(term),
        "mode": "TimelineVolRaw",
        "format": "json",
        "startdatetime": period_start.strftime("%Y%m%d000000"),
        "enddatetime": period_end.strftime("%Y%m%d235959"),
    }

    try:
        response = _retryable_http_get(session, GDELT_DOC_URL, params)
        payload = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        detail = str(exc)
        if exc.response is not None:
            try:
                snippet = exc.response.text[:200]
                detail = f"{detail} body={snippet}"
            except Exception:
                pass
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            detail=detail,
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "request_error",
            started_at,
            detail=str(exc),
        )
    except ValueError as exc:
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "parse_error",
            started_at,
            detail=str(exc),
        )
    except Exception as exc:
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "error",
            started_at,
            detail=str(exc),
        )

    timeline = payload.get("timeline", [])
    if not timeline:
        return _empty_series(period_index, 0.0), _metric(
            "gdelt",
            term,
            "ok",
            started_at,
            http_status=response.status_code,
            rows_returned=0,
        )

    dates: list[datetime] = []
    values: list[float] = []
    for item in timeline:
        raw_date = item.get("date") or item.get("datetime")
        raw_value = item.get("value")
        if raw_date is None or raw_value is None:
            continue
        dates.append(pd.to_datetime(raw_date).to_pydatetime())
        values.append(float(raw_value))

    if not dates:
        return _empty_series(period_index, 0.0), _metric(
            "gdelt",
            term,
            "ok",
            started_at,
            http_status=response.status_code,
            rows_returned=0,
        )

    series = pd.Series(values, index=pd.to_datetime(dates))
    return _align_series(series, period_index, "sum"), _metric(
        "gdelt",
        term,
        "ok",
        started_at,
        http_status=response.status_code,
        rows_returned=len(values),
    )


def fetch_google_trends_batch(
    pytrends: TrendReq,
    terms: list[str],
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], list[FetchMetric], bool]:
    started_at = perf_counter()
    try:
        pytrends.build_payload(
            kw_list=terms,
            timeframe=f"{period_start.isoformat()} {period_end.isoformat()}",
            geo="",
            gprop="",
        )
        trend_frame = pytrends.interest_over_time()
    except Exception as exc:
        detail = str(exc)
        throttled = "429" in detail or "Too Many Requests" in detail
        metrics = [
            _metric(
                "google_trends",
                term,
                "error",
                started_at,
                throttled=throttled,
                detail=detail,
            )
            for term in terms
        ]
        return {term: _empty_series(period_index) for term in terms}, metrics, throttled

    if trend_frame.empty:
        metrics = [
            _metric("google_trends", term, "ok", started_at, rows_returned=0)
            for term in terms
        ]
        return {term: _empty_series(period_index, 0.0) for term in terms}, metrics, False

    partial_mask = None
    if "isPartial" in trend_frame.columns:
        partial_mask = trend_frame["isPartial"].astype(bool)
        trend_frame = trend_frame[~partial_mask]

    series_map: dict[str, pd.Series] = {}
    metrics: list[FetchMetric] = []
    for term in terms:
        if term in trend_frame.columns:
            series = trend_frame[term].astype("float64")
            series.index = pd.to_datetime(series.index).tz_localize(None)
            series_map[term] = _align_series(series, period_index, "mean")
            metrics.append(
                _metric(
                    "google_trends",
                    term,
                    "ok",
                    started_at,
                    partial=bool(partial_mask.any()) if partial_mask is not None else False,
                    rows_returned=len(series),
                )
            )
        else:
            series_map[term] = _empty_series(period_index, 0.0)
            metrics.append(_metric("google_trends", term, "ok", started_at, rows_returned=0))
    return series_map, metrics, False


def _load_bluesky_source(
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
            metric = _metric(
                "bluesky",
                term,
                "skipped",
                perf_counter(),
                detail="skipped after earlier access block",
            )
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = metric
            continue

        series, metric = fetch_bluesky_series(session, term, period_start, granularity, period_index)
        if metric.http_status == 403:
            blocked = True
        series_map[term] = series
        metrics_map[term] = metric

    return series_map, metrics_map


def _load_gdelt_source(
    session: requests.Session,
    unique_terms: list[str],
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], dict[str, FetchMetric]]:
    series_map: dict[str, pd.Series] = {}
    metrics_map: dict[str, FetchMetric] = {}
    rate_limited = False

    for term in unique_terms:
        if rate_limited:
            metric = _metric(
                "gdelt",
                term,
                "skipped",
                perf_counter(),
                throttled=True,
                detail="skipped after earlier GDELT rate limit",
            )
            series_map[term] = _empty_series(period_index)
            metrics_map[term] = metric
            continue

        series, metric = fetch_gdelt_series(session, term, period_start, period_end, period_index)
        if metric.throttled:
            rate_limited = True
        series_map[term] = series
        metrics_map[term] = metric

    return series_map, metrics_map


def _load_google_trends_source(
    pytrends: TrendReq,
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
                    "google_trends",
                    term,
                    "skipped",
                    perf_counter(),
                    throttled=True,
                    detail="skipped after earlier Google Trends rate limit",
                )
                series_map[term] = _empty_series(period_index)
                metrics_map[term] = metric
            continue

        batch_series_map, batch_metrics, throttled = fetch_google_trends_batch(
            pytrends,
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

    LOGGER.info(
        "dataset_load_started",
        extra={
            "event": "dataset_load_started",
            "tracked_item_count": len(unique_terms),
            "granularity": granularity,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    )

    session = requests.Session()
    session.headers.update({"User-Agent": "genai-trends-dashboard/0.1"})
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))

    bluesky_series_map, bluesky_metrics = _load_bluesky_source(
        session,
        unique_terms,
        period_start,
        granularity,
        period_index,
    )
    gdelt_series_map, gdelt_metrics = _load_gdelt_source(
        session,
        unique_terms,
        period_start,
        period_end,
        period_index,
    )
    google_trends_series_map, google_trends_metrics = _load_google_trends_source(
        pytrends,
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
            "bluesky": bluesky_series_map[tracked_item],
            "gdelt": gdelt_series_map[tracked_item],
            "google_trends": google_trends_series_map[tracked_item],
        }
        source_metrics = {
            "bluesky": bluesky_metrics[tracked_item],
            "gdelt": gdelt_metrics[tracked_item],
            "google_trends": google_trends_metrics[tracked_item],
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

            for source_key, source_name in SOURCE_NAME_MAP.items():
                value = source_series[source_name].get(bucket)
                source_metric = source_metrics[source_name]
                if pd.isna(value):
                    row[f"{source_name}_frequency"] = None
                    partial_data_warning = True
                    continue

                numeric_value = round(float(value), 2)
                row[f"{source_name}_frequency"] = numeric_value
                available_sources.append(source_name)
                composite_score += numeric_value * weights[SOURCE_WEIGHT_MAP[source_key]]
                partial_data_warning = partial_data_warning or source_metric.partial

            row["available_sources"] = ", ".join(available_sources)
            row["partial_data_warning"] = partial_data_warning or len(available_sources) < len(SOURCE_NAME_MAP)
            row["composite_score"] = round(composite_score, 2)
            rows.append(row)

    dataset = pd.DataFrame(rows)
    metrics = list(bluesky_metrics.values()) + list(gdelt_metrics.values()) + list(google_trends_metrics.values())
    total_duration_ms = (perf_counter() - total_started_at) * 1000
    status = _build_status(metrics, dataset, total_duration_ms)

    LOGGER.info(
        "dataset_load_finished",
        extra={"event": "dataset_load_finished", **asdict(status)},
    )

    return dataset, asdict(status)


def build_topic_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(["period_end", "topic"], as_index=False)["composite_score"]
        .mean()
        .sort_values("period_end")
    )


def build_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "topic",
        "tracked_item",
        "time_granularity",
        "period_start",
        "period_end",
        "bluesky_frequency",
        "gdelt_frequency",
        "google_trends_frequency",
        "composite_score",
        "available_sources",
        "partial_data_warning",
    ]
    return frame[columns].sort_values(["period_end", "tracked_item"]).reset_index(drop=True)
