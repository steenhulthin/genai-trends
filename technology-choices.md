# Technology Choices

## Confirmed Choices

- Hosting targets may include GitHub Pages and `share.streamlit.io`.
- The project may use static-site-friendly technologies such as `stlite`, `shinylive`, WebAssembly-based approaches, or other true static site technologies if performance is acceptable.
- A Streamlit deployment on `share.streamlit.io` is allowed.
- The first and only live data provider is `Guardian Open Platform`.
- The primary metric is Guardian news-mention frequency.
- A cross-source composite score is not required in the simplified Guardian-only version.
- The initial tracked-item seed list should live in `tracked-items.yml`.
- The initial tracked-item seed list should contain exactly:
  - `Claude`
  - `ChatGPT`
  - `Anthropic`
  - `OpenAI`
- The primary UI should present information with charts, cards, and structured lists rather than on-screen data tables.
- The primary UI does not expose export or download controls in the simplified version.
- The visual direction should be cheerful, nerdy, and welcoming to software developers.

## Preferred Choices

- Default application stack for the first implementation: `streamlit`.
- Default deployment target for the first implementation: `share.streamlit.io`.
- Preferred fallback options if the default stack performs poorly or blocks required features:
  - `shinylive`
  - `stlite`
  - another static site technology

## Rejected Choices

- `Mastodon` is not part of the simplified first version.
- `Hacker News` is not part of the simplified first version.

## Decision Notes

- The earlier no-server restriction has been removed.
- Agents should optimize for the fastest credible path to a working first version, not for long-term stack purity.
- Simplifying to Guardian-only is preferred over maintaining a multi-source ingestion pipeline in the first version.
- The product scope is intentionally flat: each topic is directly one tracked term rather than a broader taxonomy with sub-items.
- A UX/UI-focused agent is justified for bounded interaction and visual design work, not for changing the agreed provider or topic scope without product approval.
- Revisit `GDELT Web NGrams 3.0` later if the project needs more news scale than the Guardian API provides.

## Seed Topic Option

- Use the simplified four-term Guardian-only set for the first implementation.
