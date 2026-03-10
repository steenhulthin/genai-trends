from __future__ import annotations

from datetime import date
from hashlib import sha256

import pandas as pd


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


def _stable_int(seed: str) -> int:
    return int(sha256(seed.encode("utf-8")).hexdigest()[:8], 16)


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


def _build_source_series(
    item_seed: str,
    source_name: str,
    time_index: pd.DatetimeIndex,
) -> list[float]:
    base = 30 + (_stable_int(f"{item_seed}:{source_name}:base") % 55)
    slope = 1 + (_stable_int(f"{item_seed}:{source_name}:slope") % 7)
    wave = 5 + (_stable_int(f"{item_seed}:{source_name}:wave") % 11)
    offset = _stable_int(f"{item_seed}:{source_name}:offset") % 6

    values: list[float] = []
    for index, _ in enumerate(time_index):
        period_value = base + slope * index + ((index + offset) % wave) * 1.7
        values.append(round(period_value, 2))
    return values


def generate_dataset(
    context: dict,
    tracked_items: dict,
    period_start: date,
    period_end: date,
    granularity: str,
) -> pd.DataFrame:
    time_index = _date_index(period_start, period_end, granularity)
    item_records = _item_records(tracked_items)
    source_map = SOURCE_NAME_MAP
    weights = context["metrics"]["composite_score"]["factors"]

    rows: list[dict] = []
    for record in item_records:
        topic = record["topic"]
        tracked_item = record["tracked_item"]
        item_seed = f"{topic}:{tracked_item}"

        series_by_source = {
            source_map_name: _build_source_series(item_seed, source_map_name, time_index)
            for source_map_name in source_map.values()
        }

        for index, period_end_value in enumerate(time_index):
            period_start_value = period_end_value
            row = {
                "topic": topic,
                "tracked_item": tracked_item,
                "time_granularity": granularity,
                "period_start": period_start_value.date().isoformat(),
                "period_end": period_end_value.date().isoformat(),
                "partial_data_warning": False,
            }

            active_sources: list[str] = []
            composite_score = 0.0
            for source_key, source_name in source_map.items():
                value = series_by_source[source_name][index]
                row[f"{source_name}_frequency"] = value
                composite_score += value * weights[SOURCE_WEIGHT_MAP[source_key]]
                active_sources.append(source_name)

            row["available_sources"] = ", ".join(active_sources)
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
