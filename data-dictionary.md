# Data Dictionary

This file documents the exported dashboard data so end users can understand and reuse it.

## Planned Columns

- `topic`: predefined topic name
- `tracked_item`: tracked term being measured; in the simplified first version it matches `topic`
- `time_granularity`: aggregation level, fixed to `daily` in the current implementation
- `period_start`: start timestamp or date for the aggregated interval
- `period_end`: end timestamp or date for the aggregated interval
- `news_mentions_frequency`: Guardian result count for the tracked term in the aggregated interval
- `partial_data_warning`: boolean flag that indicates Guardian data was missing or incomplete for the row

## Notes

- Keep this file aligned with the dataset shape used internally by the app.
- The tracked-term definitions should come from `tracked-items.yml`.
- The current implementation builds one row per topic, tracked item, and time window.
- `news_mentions_frequency` maps to `Guardian Open Platform`.
- Runtime fetch diagnostics are written to application log files and are not part of the CSV export.
