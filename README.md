# genai-trends

Streamlit dashboard for tracking trend signals around predefined generative AI topics and tracked items.

The current implementation combines:

- `Mastodon` hashtag timelines for social-media mentions
- `Guardian Open Platform` for news mentions
- `Hacker News` story search for discussion-oriented mention counts

The app groups those signals into three topics:

- `prompt engineering`
- `advanced software production with agents`
- `general`

## Current Status

- Topic definitions and tracked items are config-driven.
- The fetch window is currently fixed to the latest `7` days.
- The app keeps partial data visible when one or more providers fail.
- Runtime instrumentation is written to log files instead of being rendered in the UI.

## Run Locally

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Provide the required provider settings as environment variables or Streamlit secrets.

Required keys:

- `GUARDIAN_API_KEY`

Optional:

- `MASTODON_BASE_URL`
- `MASTODON_ACCESS_TOKEN`
- `APP_LOG_LEVEL`
- `APP_ENV`

You can start from:

- `.streamlit/secrets.toml.example`

3. Run the app:

```bash
streamlit run app.py
```

## Logging

The app writes runtime logs to:

- `logs/app.log`
- `logs/fetch.log`

Default logging behavior:

- `INFO` in normal/debug usage
- `ERROR` and above when `APP_ENV=prod`

## Configuration

Main project files:

- `project-context.yml`: project-level configuration and selected providers
- `tracked-items.yml`: editable tracked-item source of truth
- `spec.md`: implementation-facing specification
- `goals.md`: product goals and success criteria
- `technology-choices.md`: stack and provider decisions
- `data-dictionary.md`: exported CSV schema documentation
- `AGENTS.md`: repository-wide agent rules

## Export Schema

The filtered export is CSV and currently includes:

- `topic`
- `tracked_item`
- `time_granularity`
- `period_start`
- `period_end`
- `social_media_frequency`
- `news_mentions_frequency`
- `google_trends_frequency`
- `composite_score`
- `available_sources`
- `partial_data_warning`

See `data-dictionary.md` for details. The `google_trends_frequency` column name is retained for compatibility even though the current provider is `Hacker News`.

## Known Limitations

- Live data quality depends on external provider behavior and provider limits.
- `Guardian Open Platform` is used for simplicity; `GDELT Web NGrams 3.0` remains a later option for higher-scale news ingestion.
- Mastodon counts are derived from normalized hashtags, so multi-word tracked items are queried as compact tags such as `#systemprompt`.
- `Hacker News` is the current tertiary signal provider; `SerpApi` and `DataForSEO` remain later alternatives if Google Trends data is needed again.
- The current implementation still fetches on page load rather than using a scheduled ingestion pipeline.
