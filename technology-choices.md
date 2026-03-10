# Technology Choices

## Confirmed Choices

- Hosting targets may include GitHub Pages and `share.streamlit.io`.
- The project may use static-site-friendly technologies such as `stlite`, `shinylive`, WebAssembly-based approaches, or other true static site technologies if performance is acceptable.
- A Streamlit deployment on `share.streamlit.io` is allowed.
- The first social-data provider is `Bluesky`.
- The first news-data provider is `GDELT`.
- The first export format is `CSV`.
- The project must include a downloadable `data-dictionary.md`.

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
- Revisit `Mastodon` later as an additional social source.
- Revisit `Hacker News` later as an additional signal source.

## Seed Topic Option

- Use tracked-item option `A` for the first implementation.
