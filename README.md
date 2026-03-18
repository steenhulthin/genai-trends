# genai-trends

Streamlit dashboard for tracking Guardian news-mention signals around a small set of predefined generative AI terms.

The current implementation uses:

- `Guardian Open Platform` for news mentions

The app tracks exactly these four predefined topics:

- `Claude`
- `Anthropic`
- `ChatGPT`
- `OpenAI`

The live comparison merges them into two weekly series:

- `Claude + Anthropic`
- `ChatGPT + OpenAI`

## Current Status

- Topic definitions and tracked items are config-driven.
- The dashboard headline is `Claude versus ChatGPT`.
- The comparison period is controlled by a calendar-week range slider starting at `2022-W40`.
- The initial selected range covers the last `12` weeks.
- The dashboard runs at fixed weekly granularity.
- The app keeps partial data visible when Guardian responses are incomplete or unavailable.
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

- `APP_LOG_LEVEL`
- `APP_ENV`

You can start from:

- `.streamlit/secrets.toml.example`

3. Run the app:

```bash
streamlit run app.py
```

## Prefetch Historical Data

To save the full configured Guardian history into the repo-local `data/` folder for later fallback use, run:

```bash
python prefetch_data.py
```

This writes:

- `data/guardian_prefetch_weekly.csv`
- `data/guardian_prefetch_weekly.metadata.json`

The export covers the whole configured calendar-week period, starting at `2022-W40` and ending on the day you run the command.

Once the snapshot exists, the dashboard uses it as the historical base for weekly results and only fetches a live Guardian tail when the selected window extends past the snapshot coverage.

## Logging

The app writes runtime logs to:

- `logs/app.log`
- `logs/fetch.log`

Default logging behavior:

- `INFO` in normal/debug usage
- `ERROR` and above when `APP_ENV=prod`

## Configuration

Main project files:

- `project-context.yml`: project-level configuration and selected provider
- `tracked-items.yml`: editable tracked-term source of truth
- `spec.md`: implementation-facing specification
- `goals.md`: product goals and success criteria
- `technology-choices.md`: stack and provider decisions
- `data-dictionary.md`: exported CSV schema documentation
- `AGENTS.md`: repository-wide agent rules

## Known Limitations

- Live data quality depends on external provider behavior and provider limits.
- `Guardian Open Platform` is used for simplicity; `GDELT Web NGrams 3.0` remains a later option for higher-scale news ingestion.
- The current implementation still fetches on page load rather than using a scheduled ingestion pipeline.



