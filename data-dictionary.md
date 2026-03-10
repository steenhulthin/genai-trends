# Data Dictionary

This file documents the exported dashboard data so end users can understand and reuse it.

## Export Format

- Default export format: `CSV`

## Planned Columns

- `topic`: predefined topic name
- `tracked_item`: word or short phrase being measured
- `time_granularity`: aggregation level such as `daily`, `weekly`, or `monthly`
- `period_start`: start timestamp or date for the aggregated interval
- `period_end`: end timestamp or date for the aggregated interval
- `bluesky_frequency`: source-specific count or source-native interest value for Bluesky
- `gdelt_frequency`: source-specific count or source-native interest value for GDELT
- `google_trends_frequency`: source-specific count or source-native interest value for Google Trends
- `composite_score`: weighted combined score across enabled sources
- `available_sources`: comma-separated list of sources included in the row
- `partial_data_warning`: boolean flag that indicates a source was missing and the row is partial

## Notes

- Keep this file aligned with the actual exported CSV schema.
- The tracked-item definitions should come from `tracked-items.yml`.
- The first implementation exports one row per topic, tracked item, and time window.
- `bluesky_frequency` is currently derived from public Bluesky search results and should be treated as an approximation rather than a complete firehose count.
- Runtime fetch diagnostics are shown in the UI only and are not part of the CSV export.
