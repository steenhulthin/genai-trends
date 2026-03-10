from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from time import perf_counter
from typing import Any, Iterable

import pandas as pd
import requests
from pytrends.request import TrendReq


BLUESKY_SEARCH_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUEST_TIMEOUT = (5, 30)

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
    message: str = ""


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
    message: str = "",
) -> FetchMetric:
    return FetchMetric(
        source=source,
        tracked_item=tracked_item,
        status=status,
        duration_ms=round((perf_counter() - started_at) * 1000, 1),
        http_status=http_status,
        throttled=throttled,
        partial=partial,
        rows_returned=rows_returned,
        message=message,
    )


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


def fetch_bluesky_series(
    session: requests.Session,
    term: str,
    period_start: date,
    period_end: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()
    query = f"{_phrase_query(term)} since:{period_start.isoformat()} until:{(period_end + timedelta(days=1)).isoformat()}"
    params = {"q": query, "sort": "latest", "limit": 100}

    try:
        response = session.get(BLUESKY_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
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
            message=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric(
            "bluesky",
            term,
            "request_error",
            started_at,
            message=str(exc),
        )
    except Exception as exc:
        return _empty_series(period_index), _metric(
            "bluesky",
            term,
            "error",
            started_at,
            message=str(exc),
        )

    posts = payload.get("posts", [])
    timestamps = []
    for post in posts:
        record = post.get("record", {})
        created_at = record.get("createdAt") or post.get("indexedAt")
        if created_at:
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
        response = session.get(GDELT_DOC_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "http_error",
            started_at,
            http_status=status_code,
            throttled=status_code == 429,
            message=str(exc),
        )
    except requests.RequestException as exc:
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "request_error",
            started_at,
            message=str(exc),
        )
    except Exception as exc:
        return _empty_series(period_index), _metric(
            "gdelt",
            term,
            "error",
            started_at,
            message=str(exc),
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


def fetch_google_trends_series(
    pytrends: TrendReq,
    term: str,
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, FetchMetric]:
    started_at = perf_counter()

    try:
        pytrends.build_payload(
            kw_list=[term],
            timeframe=f"{period_start.isoformat()} {period_end.isoformat()}",
            geo="",
            gprop="",
        )
        trend_frame = pytrends.interest_over_time()
    except Exception as exc:
        message = str(exc)
        throttled = "429" in message or "Too Many Requests" in message
        return _empty_series(period_index), _metric(
            "google_trends",
            term,
            "error",
            started_at,
            throttled=throttled,
            message=message,
        )

    if trend_frame.empty or term not in trend_frame.columns:
        return _empty_series(period_index, 0.0), _metric(
            "google_trends",
            term,
            "ok",
            started_at,
            rows_returned=0,
        )

    partial = False
    series = trend_frame[term]
    series.index = pd.to_datetime(series.index).tz_localize(None)
    if "isPartial" in trend_frame.columns:
        partial_mask = trend_frame["isPartial"].astype(bool)
        partial = bool(partial_mask.any())
        series = series[~partial_mask]

    return _align_series(series.astype("float64"), period_index, "mean"), _metric(
        "google_trends",
        term,
        "ok",
        started_at,
        partial=partial,
        rows_returned=len(series),
    )


def _summarize_metrics(metrics: list[FetchMetric], total_duration_ms: float) -> pd.DataFrame:
    metric_frame = pd.DataFrame(asdict(metric) for metric in metrics)
    if metric_frame.empty:
        return pd.DataFrame(
            columns=[
                "source",
                "calls",
                "ok_calls",
                "error_calls",
                "throttled_calls",
                "partial_calls",
                "total_duration_ms",
                "avg_duration_ms",
                "max_duration_ms",
            ]
        )

    summary = (
        metric_frame.groupby("source", as_index=False)
        .agg(
            calls=("source", "count"),
            ok_calls=("status", lambda values: int((pd.Series(values) == "ok").sum())),
            error_calls=("status", lambda values: int((pd.Series(values) != "ok").sum())),
            throttled_calls=("throttled", "sum"),
            partial_calls=("partial", "sum"),
            total_duration_ms=("duration_ms", "sum"),
            avg_duration_ms=("duration_ms", "mean"),
            max_duration_ms=("duration_ms", "max"),
        )
        .sort_values("total_duration_ms", ascending=False)
    )
    summary["total_duration_ms"] = summary["total_duration_ms"].round(1)
    summary["avg_duration_ms"] = summary["avg_duration_ms"].round(1)
    summary["max_duration_ms"] = summary["max_duration_ms"].round(1)

    total_row = pd.DataFrame(
        [
            {
                "source": "all_sources",
                "calls": int(metric_frame.shape[0]),
                "ok_calls": int((metric_frame["status"] == "ok").sum()),
                "error_calls": int((metric_frame["status"] != "ok").sum()),
                "throttled_calls": int(metric_frame["throttled"].sum()),
                "partial_calls": int(metric_frame["partial"].sum()),
                "total_duration_ms": round(total_duration_ms, 1),
                "avg_duration_ms": round(metric_frame["duration_ms"].mean(), 1),
                "max_duration_ms": round(metric_frame["duration_ms"].max(), 1),
            }
        ]
    )
    return pd.concat([summary, total_row], ignore_index=True)


def generate_dataset(
    context: dict,
    tracked_items: dict,
    period_start: date,
    period_end: date,
    granularity: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    total_started_at = perf_counter()
    period_index = _date_index(period_start, period_end, granularity)
    item_records = _item_records(tracked_items)
    weights = context["metrics"]["composite_score"]["factors"]
    metrics: list[FetchMetric] = []

    session = requests.Session()
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))

    rows: list[dict[str, Any]] = []
    for record in item_records:
        topic = record["topic"]
        tracked_item = record["tracked_item"]

        bluesky_series, bluesky_metric = fetch_bluesky_series(
            session=session,
            term=tracked_item,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
            period_index=period_index,
        )
        gdelt_series, gdelt_metric = fetch_gdelt_series(
            session=session,
            term=tracked_item,
            period_start=period_start,
            period_end=period_end,
            period_index=period_index,
        )
        google_trends_series, google_trends_metric = fetch_google_trends_series(
            pytrends=pytrends,
            term=tracked_item,
            period_start=period_start,
            period_end=period_end,
            period_index=period_index,
        )
        metrics.extend([bluesky_metric, gdelt_metric, google_trends_metric])

        source_series = {
            "bluesky": bluesky_series,
            "gdelt": gdelt_series,
            "google_trends": google_trends_series,
        }
        source_metrics = {
            "bluesky": bluesky_metric,
            "gdelt": gdelt_metric,
            "google_trends": google_trends_metric,
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

    session.close()

    dataset = pd.DataFrame(rows)
    metric_frame = pd.DataFrame(asdict(metric) for metric in metrics)
    summary_frame = _summarize_metrics(metrics, (perf_counter() - total_started_at) * 1000)
    return dataset, metric_frame, summary_frame


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
