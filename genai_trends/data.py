from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from json import loads
from pathlib import Path
from time import perf_counter, sleep
from typing import Any, Iterable
import os

import pandas as pd
import requests

from genai_trends.logging_utils import get_logger


GUARDIAN_SEARCH_URL = "https://content.guardianapis.com/search"
GUARDIAN_PAGE_SIZE = 200
GUARDIAN_MAX_PAGES = 10
GUARDIAN_CALL_DELAY_SECONDS = 1.1
REQUEST_TIMEOUT = (5, 30)
BACKOFF_DELAYS_SECONDS = (1.0, 2.0)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATASET_COLUMNS = [
    "topic",
    "tracked_item",
    "time_granularity",
    "period_start",
    "period_end",
    "news_mentions_frequency",
    "partial_data_warning",
]
KEY_COLUMNS = ["topic", "tracked_item", "time_granularity", "period_start", "period_end"]

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
    cache_available: bool = False
    cache_used: bool = False
    cache_rows_used: int = 0
    cache_period_start: str | None = None
    cache_period_end: str | None = None
    live_fetch_used: bool = False
    live_fetch_start: str | None = None
    live_rows_used: int = 0


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


def _align_series(
    series: pd.Series,
    period_index: pd.DatetimeIndex,
    *,
    fill_value: float | None = 0.0,
) -> pd.Series:
    if series.empty:
        return _empty_series(period_index, fill_value)

    working = series.copy()
    working.index = pd.to_datetime(working.index)
    working = working.sort_index()
    aligned = working.groupby(level=0).sum().reindex(period_index)
    if fill_value is not None:
        aligned = aligned.fillna(fill_value)
    return aligned.astype("float64")


def _phrase_query(term: str) -> str:
    return f'"{term}"' if " " in term else term


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
    return _align_series(bucketed, period_index, fill_value=0.0)


def _retryable_http_get(session: requests.Session, url: str, params: dict[str, Any]) -> requests.Response:
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


def _snapshot_paths(provider: str, granularity: str) -> tuple[Path, Path]:
    base_name = f"{provider}_prefetch_{granularity}"
    return DATA_DIR / f"{base_name}.csv", DATA_DIR / f"{base_name}.metadata.json"


def prefetch_snapshot_version(context: dict[str, Any], granularity: str) -> str:
    provider = str(context["data_sources"]["selected"]["news_mentions"])
    dataset_path, metadata_path = _snapshot_paths(provider, granularity)
    if not dataset_path.exists():
        return "missing"

    dataset_stamp = str(dataset_path.stat().st_mtime_ns)
    if metadata_path.exists():
        return f"{dataset_stamp}:{metadata_path.stat().st_mtime_ns}"
    return dataset_stamp


def _parse_iso_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalize_boolean_column(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def _empty_dataset_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=DATASET_COLUMNS)


def _load_prefetched_dataset(
    provider: str,
    granularity: str,
    unique_terms: list[str],
    period_start: date,
    period_end: date,
) -> tuple[pd.DataFrame, dict[str, Any] | None, date | None, date | None]:
    dataset_path, metadata_path = _snapshot_paths(provider, granularity)
    if not dataset_path.exists():
        return _empty_dataset_frame(), None, None, None

    try:
        frame = pd.read_csv(dataset_path)
    except Exception as exc:
        LOGGER.warning(
            "prefetch_cache_read_failed",
            extra={
                "event": "prefetch_cache_read_failed",
                "provider": provider,
                "granularity": granularity,
                "detail": str(exc),
            },
        )
        return _empty_dataset_frame(), None, None, None

    if frame.empty:
        return _empty_dataset_frame(), None, None, None

    metadata: dict[str, Any] | None = None
    if metadata_path.exists():
        try:
            metadata = loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOGGER.warning(
                "prefetch_metadata_read_failed",
                extra={
                    "event": "prefetch_metadata_read_failed",
                    "provider": provider,
                    "granularity": granularity,
                    "detail": str(exc),
                },
            )

    frame = frame.copy()
    frame["period_start"] = pd.to_datetime(frame["period_start"], errors="coerce").dt.date
    frame["period_end"] = pd.to_datetime(frame["period_end"], errors="coerce").dt.date
    frame["news_mentions_frequency"] = pd.to_numeric(frame["news_mentions_frequency"], errors="coerce")
    frame["partial_data_warning"] = _normalize_boolean_column(frame["partial_data_warning"])

    valid_rows = frame.dropna(subset=["period_start", "period_end"])
    cache_period_start = valid_rows["period_start"].min() if not valid_rows.empty else None
    cache_period_end = valid_rows["period_end"].max() if not valid_rows.empty else None

    filtered = valid_rows[
        (valid_rows["time_granularity"] == granularity)
        & (valid_rows["tracked_item"].isin(unique_terms))
        & (valid_rows["period_end"] >= period_start)
        & (valid_rows["period_end"] <= period_end)
    ].copy()

    if filtered.empty:
        return _empty_dataset_frame(), metadata, cache_period_start, cache_period_end

    filtered["period_start"] = filtered["period_start"].map(date.isoformat)
    filtered["period_end"] = filtered["period_end"].map(date.isoformat)
    filtered = filtered[DATASET_COLUMNS].sort_values(["period_end", "tracked_item"]).reset_index(drop=True)

    LOGGER.info(
        "prefetch_cache_loaded",
        extra={
            "event": "prefetch_cache_loaded",
            "provider": provider,
            "granularity": granularity,
            "cache_rows": int(filtered.shape[0]),
            "cache_period_start": cache_period_start.isoformat() if cache_period_start else None,
            "cache_period_end": cache_period_end.isoformat() if cache_period_end else None,
        },
    )

    return filtered, metadata, cache_period_start, cache_period_end


def _template_dataset_frame(
    item_records: list[dict[str, str]],
    period_index: pd.DatetimeIndex,
    granularity: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in item_records:
        for bucket in period_index:
            bucket_value = bucket.date().isoformat()
            rows.append(
                {
                    "topic": record["topic"],
                    "tracked_item": record["tracked_item"],
                    "time_granularity": granularity,
                    "period_start": bucket_value,
                    "period_end": bucket_value,
                    "news_mentions_frequency": None,
                    "partial_data_warning": True,
                }
            )
    return pd.DataFrame(rows, columns=DATASET_COLUMNS)


def _dataset_frame_from_series_maps(
    item_records: list[dict[str, str]],
    period_index: pd.DatetimeIndex,
    granularity: str,
    news_series_map: dict[str, pd.Series],
    news_metrics: dict[str, FetchMetric],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in item_records:
        topic = record["topic"]
        tracked_item = record["tracked_item"]
        news_series = news_series_map[tracked_item]
        news_metric = news_metrics[tracked_item]

        for bucket in period_index:
            value = news_series.get(bucket)
            numeric_value = None if pd.isna(value) else round(float(value), 2)
            bucket_value = bucket.date().isoformat()
            rows.append(
                {
                    "topic": topic,
                    "tracked_item": tracked_item,
                    "time_granularity": granularity,
                    "period_start": bucket_value,
                    "period_end": bucket_value,
                    "news_mentions_frequency": numeric_value,
                    "partial_data_warning": news_metric.partial or numeric_value is None or news_metric.status != "ok",
                }
            )
    return pd.DataFrame(rows, columns=DATASET_COLUMNS)


def _overlay_dataset_frames(base: pd.DataFrame, overlay: pd.DataFrame) -> pd.DataFrame:
    if overlay.empty:
        return base
    if base.empty:
        return overlay[DATASET_COLUMNS].sort_values(["period_end", "tracked_item"]).reset_index(drop=True)

    merged = base.merge(overlay, on=KEY_COLUMNS, how="outer", suffixes=("_base", "_overlay"))
    base_values = merged["news_mentions_frequency_base"]
    overlay_values = merged["news_mentions_frequency_overlay"]
    use_overlay = overlay_values.notna() | base_values.isna()

    merged["news_mentions_frequency"] = base_values
    merged.loc[use_overlay, "news_mentions_frequency"] = overlay_values[use_overlay]

    base_warning = merged["partial_data_warning_base"].fillna(True)
    overlay_warning = merged["partial_data_warning_overlay"].fillna(True)
    merged["partial_data_warning"] = base_warning
    merged.loc[use_overlay, "partial_data_warning"] = overlay_warning[use_overlay]

    return merged[DATASET_COLUMNS].sort_values(["period_end", "tracked_item"]).reset_index(drop=True)


def _live_fetch_start(
    period_start: date,
    period_end: date,
    cache_metadata: dict[str, Any] | None,
    cache_period_end: date | None,
) -> date | None:
    if cache_period_end is None:
        return period_start

    coverage_end = _parse_iso_date(cache_metadata.get("period_end")) if cache_metadata else None
    if coverage_end is None:
        coverage_end = cache_period_end

    if period_end <= coverage_end:
        return None

    return max(period_start, cache_period_end)


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
    timestamps: list[str] = []
    total_rows = 0
    partial = False
    last_status_code: int | None = None

    try:
        for page in range(1, GUARDIAN_MAX_PAGES + 1):
            params = {
                "api-key": api_key,
                "q": _phrase_query(term),
                "from-date": period_start.isoformat(),
                "to-date": period_end.isoformat(),
                "page-size": GUARDIAN_PAGE_SIZE,
                "page": page,
                "order-by": "newest",
            }

            if page > 1:
                sleep(GUARDIAN_CALL_DELAY_SECONDS)

            response = _retryable_http_get(session, GUARDIAN_SEARCH_URL, params)
            last_status_code = response.status_code
            payload = response.json()
            payload_response = payload.get("response", {})
            results = payload_response.get("results", [])
            if not isinstance(results, list):
                raise ValueError("guardian search did not return a results list")
            if not results:
                break

            timestamps.extend(item.get("webPublicationDate") for item in results if item.get("webPublicationDate"))
            total_rows += len(results)

            current_page = payload_response.get("currentPage", page)
            total_pages = payload_response.get("pages", page)
            if not isinstance(current_page, int) or not isinstance(total_pages, int):
                raise ValueError("guardian search did not return integer pagination fields")
            if current_page >= total_pages:
                break
            if page == GUARDIAN_MAX_PAGES:
                partial = True
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

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), _metric(
        "guardian",
        term,
        "ok",
        started_at,
        http_status=last_status_code,
        partial=partial,
        rows_returned=total_rows,
    )


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
    for term in unique_terms:
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


def _build_status(
    metrics: list[FetchMetric],
    dataset: pd.DataFrame,
    total_duration_ms: float,
    *,
    cache_available: bool,
    cache_used: bool,
    cache_rows_used: int,
    cache_period_start: date | None,
    cache_period_end: date | None,
    live_fetch_start: date | None,
    live_rows_used: int,
) -> LoadStatus:
    return LoadStatus(
        total_duration_ms=round(total_duration_ms, 1),
        api_calls=len(metrics),
        throttled_calls=sum(1 for metric in metrics if metric.throttled),
        partial_calls=sum(1 for metric in metrics if metric.partial),
        error_calls=sum(1 for metric in metrics if metric.status not in {"ok", "skipped"}),
        partial_rows=int(dataset["partial_data_warning"].sum()) if not dataset.empty else 0,
        cache_available=cache_available,
        cache_used=cache_used,
        cache_rows_used=cache_rows_used,
        cache_period_start=cache_period_start.isoformat() if cache_period_start else None,
        cache_period_end=cache_period_end.isoformat() if cache_period_end else None,
        live_fetch_used=live_fetch_start is not None,
        live_fetch_start=live_fetch_start.isoformat() if live_fetch_start else None,
        live_rows_used=live_rows_used,
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
    selected_sources = context["data_sources"]["selected"]
    provider = str(selected_sources["news_mentions"])

    LOGGER.info(
        "dataset_load_started",
        extra={
            "event": "dataset_load_started",
            "tracked_item_count": len(unique_terms),
            "granularity": granularity,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "news_provider": provider,
        },
    )

    template_frame = _template_dataset_frame(item_records, period_index, granularity)
    cached_frame, cache_metadata, cache_period_start, cache_period_end = _load_prefetched_dataset(
        provider,
        granularity,
        unique_terms,
        period_start,
        period_end,
    )
    combined = _overlay_dataset_frames(template_frame, cached_frame)

    live_fetch_start = _live_fetch_start(period_start, period_end, cache_metadata, cache_period_end)
    live_frame = _empty_dataset_frame()
    metrics: list[FetchMetric] = []

    if live_fetch_start is not None:
        live_period_index = _date_index(live_fetch_start, period_end, granularity)
        session = requests.Session()
        session.headers.update({"User-Agent": "genai-trends-dashboard/0.1"})
        news_series_map, news_metrics = _load_guardian_source(
            session,
            unique_terms,
            live_fetch_start,
            period_end,
            granularity,
            live_period_index,
        )
        session.close()

        live_frame = _dataset_frame_from_series_maps(
            item_records,
            live_period_index,
            granularity,
            news_series_map,
            news_metrics,
        )
        combined = _overlay_dataset_frames(combined, live_frame)
        metrics = list(news_metrics.values())

        LOGGER.info(
            "dataset_live_tail_loaded",
            extra={
                "event": "dataset_live_tail_loaded",
                "live_fetch_start": live_fetch_start.isoformat(),
                "live_fetch_end": period_end.isoformat(),
                "live_rows": int(live_frame.shape[0]),
            },
        )

    dataset = combined[DATASET_COLUMNS].sort_values(["period_end", "tracked_item"]).reset_index(drop=True)
    total_duration_ms = (perf_counter() - total_started_at) * 1000
    status = _build_status(
        metrics,
        dataset,
        total_duration_ms,
        cache_available=cache_period_end is not None,
        cache_used=not cached_frame.empty,
        cache_rows_used=int(cached_frame.shape[0]),
        cache_period_start=cache_period_start,
        cache_period_end=cache_period_end,
        live_fetch_start=live_fetch_start,
        live_rows_used=int(live_frame.shape[0]),
    )

    LOGGER.info("dataset_load_finished", extra={"event": "dataset_load_finished", **asdict(status)})

    return dataset, asdict(status)





