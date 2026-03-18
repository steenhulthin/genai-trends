from __future__ import annotations

from genai_trends.config import ROOT, load_project_context, load_tracked_items
from genai_trends.prefetch import export_prefetch_snapshot


def main() -> None:
    context = load_project_context()
    tracked_items = load_tracked_items()
    result = export_prefetch_snapshot(context=context, tracked_items=tracked_items)
    metadata = result["metadata"]

    dataset_file = result["dataset_path"].relative_to(ROOT)
    metadata_file = result["metadata_path"].relative_to(ROOT)

    print(f"Saved dataset: {dataset_file}")
    print(f"Saved metadata: {metadata_file}")
    print(f"Period: {metadata['period_start']} to {metadata['period_end']}")
    print(f"Granularity: {metadata['granularity']}")
    print(f"Rows: {metadata['row_count']}")

    load_status = metadata["load_status"]
    if int(load_status["error_calls"]) > 0 or int(load_status["partial_calls"]) > 0:
        print(
            "Warning: the snapshot completed with partial data. "
            "Check the metadata file and application logs before using it as fallback input."
        )


if __name__ == "__main__":
    main()
