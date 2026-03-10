# Project Specification

## Functional Requirements

- The dashboard must present three predefined topics:
  - `prompt engineering`
  - `advanced software production with agents`
  - `general`
- The dashboard must support tracked items that are either single words or short phrases representing one concept.
- The dashboard must show grouped trend signals from:
  - social media
  - news mentions
  - a tertiary discussion or interest source
- Source priority must be treated as:
  - social media: highest priority
  - news mentions: second priority
  - tertiary discussion or interest source: third priority
- The first implementation must use:
  - `Mastodon` hashtag timelines for social media
  - `Guardian Open Platform` for news mentions
  - `Hacker News` story search for the tertiary trend/discussion signal
- The dashboard must show both:
  - source-specific frequency values
  - a composite popularity score
- The dashboard must allow users to:
  - select a topic and drill down into its tracked words or phrases
  - clearly see the hierarchy from topic to tracked items in the main UI
  - select time granularity: daily, weekly, or monthly
  - inspect the currently active fetch window
  - download the currently filtered data in a standard file format
- The dashboard must allow users to download `data-dictionary.md`.
- The primary dashboard UI must not render raw data tables as part of the normal on-screen experience.
- Tabular data may be used for exported files or internal debugging, but not as the main presentation layer.
- The default time granularity must be daily.
- Data must be loaded when the dashboard page is loaded.
- Data must be reloaded when the user changes filters or refreshes the browser.

## Data Model

- `topic`: a predefined group of related tracked items.
- `tracked item`: a word or short phrase representing one concept, for example `vibe coding` or `Ralph Wiggum Loop`.
- `topic membership`: a tracked item may appear in more than one topic when the concept overlaps naturally.
- `source frequency`: the count or source-native interest signal returned for one tracked item within one time window and one source.
- `composite popularity score`: a weighted combination of source frequencies across all enabled sources.
- `time window`: the selected aggregation interval, initially daily, weekly, or monthly.

## Scoring

- The first version should compute a simple weighted composite score using this model:
  - `social_frequency * social_factor + news_frequency * news_factor + google_trends_frequency * google_trends_factor`
- The initial factor values are:
  - `social_factor = 0.5`
  - `news_factor = 0.3`
  - `google_trends_factor = 0.2`
- Agents should keep the scoring implementation simple and easy to change.
- If one source fails, the app should keep the remaining data visible and show a partial-data warning instead of failing hard.

## Non-Functional Requirements

- The dashboard should be intuitive to use with both mouse and keyboard.
- All controls should be reachable by keyboard.
- The interface should degrade gracefully when one or more data sources fail.
- Agents should prefer implementations that keep the dashboard responsive during page load and filter changes.
- The visual style should feel cheerful, nerdy, and welcoming to software developers.
- The layout should emphasize information hierarchy, visual scanning, and narrative flow over dense data presentation.

## Interfaces

- Data inputs should come from open or freely available sources where practical.
- The first implementation should organize data by source and topic before presenting composite scores.
- Export output should use `CSV` in the first version.
- The project should include a `data-dictionary.md` file that documents export columns, meanings, and examples.
- The UI should expose `data-dictionary.md` as a downloadable artifact.
- The main UI should prefer charts, cards, badges, and structured lists over generic tables.

## Validation

- Source-specific trend data should be checked against at least one other open or freely available source when feasible.
- Composite scoring should be implemented in a way that can be inspected and adjusted easily.
- The first version should favor transparent validation over a complex scoring formula.

## Notes

- The initial topic set is enough for the first release.
- Agents should treat the topic taxonomy as predefined, not inferred from the data.
- Use tracked-item seed list option `A` as the first implementation set.
- Store the concrete tracked-item seed list in `tracked-items.yml` so it is easy to change later or evaluate dynamically in a future iteration.
- If a tracked item fits more than one topic, include it in each relevant topic.
- The export and scoring schema retains the legacy `google_trends_frequency` field name for compatibility even when the configured tertiary provider is not Google Trends.
- When Mastodon is the social source, tracked items are normalized into compact hashtag slugs such as `system prompt -> #systemprompt`.
- The current implementation keeps the live fetch window fixed to the latest seven days while the collectors are being stabilized.
- The intended information architecture is `topic -> tracked items -> signal detail`, and that hierarchy should be obvious without reading exported data.

## Deferred Options

- Evaluate `Reddit API` later as an additional social-data source if free access becomes practical again.
- Evaluate richer `Hacker News` coverage later if comment counts or alternate search providers are needed.
- Evaluate `GDELT Web NGrams 3.0` later if the project needs a higher-scale news pipeline.
- Evaluate `SerpApi` or `DataForSEO` later as alternative Google Trends providers.
