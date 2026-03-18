# Project Specification

## Functional Requirements

- The dashboard must present five predefined topics:
  - `AI`
  - `Anthropic`
  - `OpenAI`
  - `Claude`
  - `ChatGPT`
- The first simplified version must treat each topic as a single tracked term.
- The dashboard must use `Guardian Open Platform` as its only live data source.
- The dashboard must show Guardian news-mention frequency over time for each predefined topic.
- The dashboard must allow users to:
  - select one of the predefined topics
  - compare the predefined topics within the same time window
  - inspect the currently active fetch window
- The primary dashboard UI must not render raw data tables as part of the normal on-screen experience.
- The default time granularity must be daily.
- Data must be loaded when the dashboard page is loaded.
- Data must be reloaded when the user changes filters or refreshes the browser.

## Data Model

- `topic`: one of the five predefined tracked terms.
- `tracked item`: the same value as the topic in the first simplified version.
- `news mention frequency`: the Guardian result count or equivalent Guardian-native count returned for one topic within one time window.
- `time window`: the selected aggregation interval, fixed to daily in the simplified version.

## Metrics

- The first version should use Guardian news-mention frequency as the primary metric.
- A cross-source composite popularity score is not required in the Guardian-only version.
- If the Guardian source fails, the app should keep the surrounding UI visible and show a clear warning instead of failing hard.

## Non-Functional Requirements

- The dashboard should be intuitive to use with both mouse and keyboard.
- All controls should be reachable by keyboard.
- The interface should degrade gracefully when Guardian data is unavailable.
- Agents should prefer implementations that keep the dashboard responsive during page load and filter changes.
- The visual style should feel cheerful, nerdy, and welcoming to software developers.
- The layout should emphasize visual scanning and simple comparisons over dense data presentation.

## Interfaces

- Data inputs should come from `Guardian Open Platform` for the first version.
- The first implementation should organize data by topic before presenting comparisons.
- The main UI should prefer charts, cards, badges, and structured lists over generic tables.

## Validation

- Guardian query logic and result-count handling should be implemented in a way that can be inspected and adjusted easily.
- The first version should favor transparent counting over derived scoring.

## Notes

- The initial topic set is enough for the first release.
- Agents should treat the topic list as predefined, flat, and not inferred from the data.
- Store the concrete topic seed list in `tracked-items.yml` so it is easy to change later.
- The initial tracked-item seed list should contain exactly the same five values as the topic list.
- The current implementation keeps the live fetch window fixed to the latest one year.
- The intended information architecture is a flat topic-first browse experience rather than a deeper topic-to-subtopic hierarchy.

## Deferred Options

- Evaluate `GDELT Web NGrams 3.0` later if the project needs a higher-scale news pipeline than the Guardian API provides.
