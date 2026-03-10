# Technology Choices

## Confirmed Choices

- Hosting targets may include GitHub Pages and `share.streamlit.io`.
- The project may use static-site-friendly technologies such as `stlite`, `shinylive`, WebAssembly-based approaches, or other true static site technologies if performance is acceptable.
- A Streamlit deployment on `share.streamlit.io` is allowed.
- The first social-data provider is `Mastodon` hashtag timelines.
- The first news-data provider is `Guardian Open Platform`.
- The first tertiary trend/discussion provider is `Hacker News` search.
- The first export format is `CSV`.
- The project must include a downloadable `data-dictionary.md`.
- The initial composite weights are `social=0.5`, `news=0.3`, and `google_trends=0.2`.
- If a source fails, the UI should warn and continue showing the remaining data.
- The initial tracked-item seed list should live in `tracked-items.yml`.
- The export schema keeps the legacy `google_trends_frequency` field name for the tertiary signal to avoid breaking downstream CSV consumers.
- The primary UI should present information with charts, cards, and structured lists rather than on-screen data tables.
- The visual direction should be cheerful, nerdy, and welcoming to software developers.

## Preferred Choices

- Default application stack for the first implementation: `streamlit`.
- Default deployment target for the first implementation: `share.streamlit.io`.
- Preferred fallback options if the default stack performs poorly or blocks required features:
  - `shinylive`
  - `stlite`
  - another static site technology

## Rejected Choices

- None currently.

## Decision Notes

- The earlier no-server restriction has been removed.
- Agents should optimize for the fastest credible path to a working first version, not for long-term stack purity.
- If a static-first approach materially improves performance or hosting simplicity without slowing delivery too much, agents may recommend it.
- Server-side fetching and caching are allowed for the Streamlit path.
- Client-side or static-friendly fetching remains a soft preference when it does not complicate delivery.
- Mastodon tracked items are queried as normalized hashtags rather than full-text searches.
- A UX/UI-focused agent is justified for the next interface pass because the product now has explicit hierarchy and visual-tone requirements beyond basic implementation.
- A UX/UI-focused agent should be used for bounded interaction and visual design work, not for changing core data-source or scoring decisions without product approval.
- Revisit `Reddit API` later if free authenticated access becomes practical again.
- Revisit expanded `Hacker News` coverage later if story-only counts prove too thin.
- Revisit `GDELT Web NGrams 3.0` later if the project needs more news scale than the Guardian API provides.
- Revisit `SerpApi` or `DataForSEO` later if Google Trends data becomes a requirement again.

## Seed Topic Option

- Use tracked-item option `A` for the first implementation.
