# Project Goals

## Purpose

The project should help users understand which generative AI topics and terms are gaining or losing momentum over time.

The dashboard should group trend signals from social media, news mentions, and Google Trends, with social media as the highest-priority source, news as second priority, and Google Trends as third priority.

## Audience

- Primary users: people building software with AI agents, including practitioners working with vibe coding, agent-based software production, and AI-driven automation.
- Secondary users: journalists and other people who want a structured view of current generative AI trends.

## Why This Project Should Exist

The dashboard should help users identify which generative AI topics, concepts, and terms are increasing in relevance so they can decide what to learn, monitor, write about, or build around.

## Success Criteria

- A live dashboard is available.
- The dashboard covers the initial topic set:
  - `prompt engineering`
  - `advanced software production with agents`
  - `general`
- Users can drill down from a topic into the tracked words or phrases within that topic.
- Users can view trend data over time with adjustable granularity.
- Users can export the currently filtered data in a standard file format.
- The dashboard degrades gracefully with a friendly fallback state or error message when data cannot be loaded.

## Non-Goals

- The first version does not need automatic topic discovery.
- The first version does not need real-time streaming updates.
- The first version does not need user accounts or write-back features.

## Constraints

- Topics are predefined for the first version.
- A tracked item may be a single word or a short phrase representing one concept.
- The initial topic set is intentionally small so agents can ship a working first version quickly.

## Open Questions

- Which exact social media and news sources are acceptable for the first implementation?
- Which export format should be the default in the first version if only one format is supported?
- How should topic membership be maintained when a term could belong to more than one topic?

