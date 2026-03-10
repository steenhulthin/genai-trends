from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

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
    term: str,
    period_start: date,
    period_end: date,
    granularity: str,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, bool]:
    query = f"{_phrase_query(term)} since:{period_start.isoformat()} until:{(period_end + timedelta(days=1)).isoformat()}"
    params = {"q": query, "sort": "latest", "limit": 100}

    try:
        response = requests.get(BLUESKY_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return _empty_series(period_index), True

    posts = payload.get("posts", [])
    timestamps = []
    for post in posts:
        record = post.get("record", {})
        created_at = record.get("createdAt") or post.get("indexedAt")
        if created_at:
            timestamps.append(created_at)

    return _bucket_series_from_timestamps(timestamps, period_index, granularity), False


def fetch_gdelt_series(
    term: str,
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, bool]:
    params = {
        "query": _phrase_query(term),
        "mode": "TimelineVolRaw",
        "format": "json",
        "startdatetime": period_start.strftime("%Y%m%d000000"),
        "enddatetime": period_end.strftime("%Y%m%d235959"),
    }

    try:
        response = requests.get(GDELT_DOC_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return _empty_series(period_index), True

    timeline = payload.get("timeline", [])
    if not timeline:
        return _empty_series(period_index, 0.0), False

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
        return _empty_series(period_index, 0.0), False

    series = pd.Series(values, index=pd.to_datetime(dates))
    return _align_series(series, period_index, "sum"), False


def fetch_google_trends_series(
    term: str,
    period_start: date,
    period_end: date,
    period_index: pd.DatetimeIndex,
) -> tuple[pd.Series, bool]:
    try:
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        pytrends.build_payload(
            kw_list=[term],
            timeframe=f"{period_start.isoformat()} {period_end.isoformat()}",
            geo="",
            gprop="",
        )
        trend_frame = pytrends.interest_over_time()
    except Exception:
        return _empty_series(period_index), True

    if trend_frame.empty or term not in trend_frame.columns:
        return _empty_series(period_index, 0.0), False

    series = trend_frame[term]
    series.index = pd.to_datetime(series.index).tz_localize(None)
    if "isPartial" in trend_frame.columns:
        partial_mask = trend_frame["isPartial"].astype(bool)
        series = series[~partial_mask]

    return _align_series(series.astype("float64"), period_index, "mean"), False


def generate_dataset(
    context: dict,
    tracked_items: dict,
    period_start: date,
    period_end: date,
    granularity: str,
) -> pd.DataFrame:
    period_index = _date_index(period_start, period_end, granularity)
    item_records = _item_records(tracked_items)
    weights = context["metrics"]["composite_score"]["factors"]

    rows: list[dict] = []
    for record in item_records:
        topic = record["topic"]
        tracked_item = record["tracked_item"]

        bluesky_series, bluesky_partial = fetch_bluesky_series(
            term=tracked_item,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
            period_index=period_index,
        )
        gdelt_series, gdelt_partial = fetch_gdelt_series(
            term=tracked_item,
            period_start=period_start,
            period_end=period_end,
            period_index=period_index,
        )
        google_trends_series, google_trends_partial = fetch_google_trends_series(
            term=tracked_item,
            period_start=period_start,
            period_end=period_end,
            period_index=period_index,
        )

        source_series = {
            "bluesky": bluesky_series,
            "gdelt": gdelt_series,
            "google_trends": google_trends_series,
        }
        source_partials = {
            "bluesky": bluesky_partial,
            "gdelt": gdelt_partial,
            "google_trends": google_trends_partial,
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
                if pd.isna(value):
                    row[f"{source_name}_frequency"] = None
                    partial_data_warning = True
                    continue

                numeric_value = round(float(value), 2)
                row[f"{source_name}_frequency"] = numeric_value
                available_sources.append(source_name)
                composite_score += numeric_value * weights[SOURCE_WEIGHT_MAP[source_key]]
                partial_data_warning = partial_data_warning or source_partials[source_name]

            row["available_sources"] = ", ".join(available_sources)
            row["partial_data_warning"] = partial_data_warning or len(available_sources) < len(SOURCE_NAME_MAP)
            row["composite_score"] = round(composite_score, 2)
            rows.append(row)

    return pd.DataFrame(rows)


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
