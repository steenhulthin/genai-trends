# Project Goals

## Purpose

The project should help users understand which of a small set of predefined generative AI terms are gaining or losing momentum in Guardian coverage over time.

The dashboard should present Guardian news-mention data for four predefined terms: `Claude`, `Anthropic`, `ChatGPT`, and `OpenAI`.
The main product framing should be `Claude versus ChatGPT`, with `Claude + Anthropic` compared against `ChatGPT + OpenAI`.

## Audience

- Primary users: people building software with AI tools and agents who want a quick read on which major AI terms are showing up more often in news coverage.
- Secondary users: journalists and other people who want a lightweight view of current generative AI news momentum.

## Why This Project Should Exist

The dashboard should help users identify which major AI terms are increasing in news relevance so they can decide what to learn, monitor, write about, or build around.

## Success Criteria

- A live dashboard is available.
- The dashboard covers exactly these four predefined topics:
  - `Claude`
  - `Anthropic`
  - `ChatGPT`
  - `OpenAI`
- The dashboard headline should frame the product as `Claude versus ChatGPT`.
- Users can compare `Claude + Anthropic` against `ChatGPT + OpenAI`.
- Users can adjust the time window with a weekly slider that defaults to roughly half a year.
- Users can view trend data over time at weekly granularity.
- The primary interface presents information through charts, cards, or structured lists rather than raw data tables.
- The visual tone feels cheerful, nerdy, and welcoming to software developers.
- The dashboard degrades gracefully with a friendly fallback state or error message when Guardian data cannot be loaded.

## Non-Goals

- The first version does not need automatic topic discovery.
- The first version does not need additional live data providers beyond Guardian.
- The first version does not need user accounts or write-back features.

## Constraints

- Topics are predefined for the first version.
- The initial scope is intentionally flat: each topic is also the tracked term being measured.
- The initial tracked-term list should live in a dedicated file so it can be updated without rewriting the higher-level project documents.
- The initial topic set is intentionally small so agents can ship a working first version quickly.
- The main on-screen experience should not depend on raw tabular presentation.

## Deferred Options

- Revisit additional news or discussion sources later if the Guardian-only version proves too narrow.
- Revisit broader topic sets later if the four-term version is too limited.
