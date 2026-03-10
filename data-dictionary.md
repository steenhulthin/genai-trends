# Data Dictionary

This file documents the exported dashboard data so end users can understand and reuse it.

## Export Format

- Default export format: `CSV`

## Planned Columns

- `topic`: predefined topic name
- `tracked_item`: word or short phrase being measured
- `source`: source name such as `bluesky`, `gdelt`, or `google_trends`
- `time_granularity`: aggregation level such as `daily`, `weekly`, or `monthly`
- `period_start`: start timestamp or date for the aggregated interval
- `period_end`: end timestamp or date for the aggregated interval
- `source_frequency`: source-specific count or source-native interest value
- `composite_score`: weighted combined score across enabled sources

## Notes

- Column names and exact value conventions may be refined during implementation.
- Keep this file aligned with the actual exported CSV schema.
- The tracked-item definitions should come from `tracked-items.yml`.
