from __future__ import annotations

from datetime import date, datetime, timezone
from json import dumps
from pathlib import Path
from typing import Any

from genai_trends.config import ROOT
from genai_trends.data import generate_dataset
from genai_trends.logging_utils import get_logger


LOGGER = get_logger("genai_trends.prefetch")


def full_period_bounds(context: dict[str, Any], today: date | None = None) -> tuple[date, date]:
    current_day = today or date.today()
    start_year = int(context["time"]["calendar_start_year"])
    start_week = int(context["time"]["calendar_start_week"])
    period_start = date.fromisocalendar(start_year, start_week, 1)
    return period_start, current_day


def default_prefetch_dir() -> Path:
    return ROOT / "data"


def export_prefetch_snapshot(
    context: dict[str, Any],
    tracked_items: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    granularity = str(context["time"]["granularity"]["default"])
    period_start, period_end = full_period_bounds(context)
    dataset, load_status = generate_dataset(
        context=context,
        tracked_items=tracked_items,
        period_start=period_start,
        period_end=period_end,
        granularity=granularity,
    )

    target_dir = output_dir or default_prefetch_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    provider = str(context["data_sources"]["selected"]["news_mentions"])
    dataset_filename = f"{provider}_prefetch_{granularity}.csv"
    metadata_filename = f"{provider}_prefetch_{granularity}.metadata.json"
    dataset_path = target_dir / dataset_filename
    metadata_path = target_dir / metadata_filename

    dataset.to_csv(dataset_path, index=False)

    tracked_terms = sorted(
        item
        for topic_data in tracked_items["topics"].values()
        for item in topic_data["items"]
    )
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "granularity": granularity,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "row_count": int(dataset.shape[0]),
        "tracked_terms": tracked_terms,
        "files": {
            "dataset": dataset_filename,
            "metadata": metadata_filename,
        },
        "load_status": load_status,
    }
    metadata_path.write_text(dumps(metadata, indent=2), encoding="utf-8")

    LOGGER.info(
        "prefetch_snapshot_written",
        extra={
            "event": "prefetch_snapshot_written",
            "provider": provider,
            "granularity": granularity,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "row_count": int(dataset.shape[0]),
            "dataset_file": dataset_filename,
            "metadata_file": metadata_filename,
        },
    )

    return {
        "dataset_path": dataset_path,
        "metadata_path": metadata_path,
        "metadata": metadata,
    }
