# Prompt Log

Let's start this project from scratch. I want to be agent driven as much as possible. Start by adding a root agents file. A want a rule saying that every prompt and every agent answer should be logged in a prompt.md file (not other context, just the exact raw pormpts).

Added a root [AGENTS.md](e:\prj\dagens_dashboard\genai-trends\AGENTS.md) with an append-only prompt logging rule, and created [prompt.md](e:\prj\dagens_dashboard\genai-trends\prompt.md) at the repo root to hold the raw transcript. The rule states that only exact raw user prompts and exact raw agent responses should be logged there, with no tool output or extra context.

# Context from my IDE setup:

## Active file: prompt.md

## Active selection of the file:
e:\prj\dagens_dashboard\genai-trends
## Open tabs:
- prompt.md: prompt.md
- AGENTS.md: AGENTS.md

## My request for Codex:
I would like the following rules: 
1. never leak specific information on (software) environment that the project is runnng on. (for inistance never mention absolute paths - relative paths in the project folder is fine). 
2. refactor the agents file into more specific agents file or skills whenever it makes sense
3. agents should do as much of the work as possible

Updated `AGENTS.md` to add three repository-wide rules: never expose environment-specific details in user-facing output, keep the root agent file minimal by moving specialized guidance into narrower agent files or skills when appropriate, and bias agents toward doing the work directly instead of handing steps back to the user. I also kept the existing prompt logging rule unchanged.

# Context from my IDE setup:

## Active file: prompt.md

## Active selection of the file:
e:\prj\dagens_dashboard\genai-trends
## Open tabs:
- prompt.md: prompt.md
- AGENTS.md: AGENTS.md

## My request for Codex:
PLEASE IMPLEMENT THIS PLAN:
# Agent Execution Bias Scaffolding

## Summary
Adopt a `Planner -> Executor -> Verifier` operating model as the default interpretation of `Agent Execution Bias`, with low user gating. Do not use a Ralph Wiggum loop as the primary workflow. Instead, reserve a bounded critique/retry loop for verification failures or unclear first-pass output.

This gives you high autonomy without turning the repo into an uncontrolled retry machine. It also matches your current preference to let agents do most of the work while keeping the root rules minimal.

## Key Changes
- Keep the root `AGENTS.md` limited to repo-wide policies only.
- Add role-specific instructions for three agent responsibilities:
  - `planner`: converts requests into concrete tasks, defines success criteria, and decides whether work can proceed without asking.
  - `executor`: performs the implementation directly, preferring action over delegation.
  - `verifier`: checks acceptance criteria, tests, and regressions; can trigger one bounded retry if the result is close but incomplete.
- Add reusable skills for repeated workflows instead of packing behavior into the root file:
  - `task-decomposition`: break requests into executable units with stop conditions.
  - `implementation-defaults`: bias toward direct edits, local verification, and concise reporting.
  - `verification-gate`: define when to retry, when to stop, and when to escalate to the user.
- Define an escalation policy in instructions:
  - agents proceed by default;
  - they stop only for destructive actions, permissions, missing product intent, or conflicting constraints.
- Define a bounded retry policy instead of an open-ended Ralph loop:
  - maximum 1 planned self-repair cycle after verifier failure;
  - second failure escalates with a concise blocker report;
  - no indefinite “think-critique-retry” recursion.

## Options Evaluated
- `Single Agent`
  - simplest scaffolding;
  - weaker separation of planning, execution, and verification;
  - acceptable for tiny repos, but less durable as the project grows.
- `Planner-Executor`
  - best default for this repo now;
  - easy to encode in small agent files and skills;
  - scales cleanly once project goals arrive.
- `Ralph Wiggum Loop`
  - useful as a local recovery mechanism;
  - poor primary control model because it can hide weak specs behind repeated retries;
  - should be a verifier-side fallback, not the default architecture.
- `Rules Only`
  - fastest to start;
  - too dependent on base model behavior;
  - weak for consistency across future tasks.
- `Roles + Skills`
  - recommended;
  - keeps root policy small and moves behavior into focused, reusable scaffolding.
- `Workflow Scripts`
  - useful later if the process becomes repetitive;
  - premature before the project goals and stack are known.

## Test Plan
- Validate that a generic feature request is handled as:
  1. planner defines task and acceptance criteria,
  2. executor performs the work,
  3. verifier checks and either accepts or triggers one retry.
- Validate that a product-level ambiguity causes a question before execution.
- Validate that a normal implementation request does not bounce work back to the user unnecessarily.
- Validate that environment-specific details are not exposed in user-facing responses.
- Validate that prompt logging still records only raw user prompts and raw agent responses.

## Assumptions
- Initial scaffolding should optimize for future growth, not just the current empty repo state.
- The first version should be instruction-driven, not script-driven.
- Low gating means “act unless blocked,” not “act destructively without restraint.”
- A bounded verifier retry satisfies the useful part of a Ralph loop without making it the core workflow.

Implemented the scaffolding. `AGENTS.md` now stays at the repo-policy level and defines the default `planner -> executor -> verifier` model, low gating, skill-first specialization, and a one-retry verification cap. I added role-specific instruction files in `agents/planner/AGENTS.md`, `agents/executor/AGENTS.md`, and `agents/verifier/AGENTS.md`, plus three repo-local skills in `skills/task-decomposition`, `skills/implementation-defaults`, and `skills/verification-gate`.

Verification was manual: I reread the root rules, role handoff files, and skill definitions, and I scanned the new scaffolding outside `prompt.md` for accidental environment leakage. I could not use the external skill initializer or validator because direct Python execution is blocked here, so the skill structure and metadata were created and checked by hand.

# Context from my IDE setup:

## Open tabs:
- prompt.md: prompt.md
- AGENTS.md: AGENTS.md

## My request for Codex:
I would like to write the goals and specifications in a file so I (and agents) can read them at any time. Create these files. 
I also have some fixed technology choices that I would like to specify in a file. 
These files do not need to append - git will handle any changes to these files.

Created three persistent project files: [goals.md](goals.md) for product goals and success criteria, [spec.md](spec.md) for implementation-facing requirements and interfaces, and [technology-choices.md](technology-choices.md) for fixed and preferred stack decisions. They are structured as editable templates and are separate from the append-only `prompt.md` log.

# Context from my IDE setup:

## Active file: technology-choices.md

## Open tabs:
- technology-choices.md: technology-choices.md
- spec.md: spec.md
- goals.md: goals.md
- AGENTS.md: AGENTS.md
- prompt.md: prompt.md

## My request for Codex:
go through golas.md, spec.md and technology-choices.md and come with corrections, suggestions and questions to clarify the agent work in the project.

Main issues first:

1. `technology-choices.md` contains the most important contradiction: `streamlit` is listed as the first preference, but `don't use that requires a server` is listed as a rejection. In practice, Streamlit usually implies a running server, so that conflicts with your stated deployment constraint.
2. `goals.md` still mixes template instructions with actual project content. For agent work, this should become declarative project truth only, otherwise agents have to guess what is guidance versus what is actual intent.
3. `goals.md` and `spec.md` are still too ambiguous on the core data model: what a `topic` is, what a `word trend` is, how `popularity` is calculated, what sources are allowed, and how often data should update.
4. `spec.md` is missing the implementation-critical constraints agents will need to act autonomously: deployment target, static-hosting limits, accessibility baseline, acceptable data freshness, fallback behavior, and validation rules.
5. Several lines need wording cleanup because they are unclear or grammatically broken enough that agents may interpret them inconsistently.

Corrections and suggestions:

- In `goals.md`, remove the instructional placeholder bullets and keep only project facts.
- Rewrite the purpose more concretely. For example: `The project should help users understand which generative AI topics and terms are gaining or losing momentum over time.`
- Tighten the audience definition. Separate primary users from secondary users.
- Rewrite the “why” section in outcome terms, not motivation prose. Focus on what decision the user can make after seeing the dashboard.
- Make success criteria measurable. `Live dashboard` and `runs smoothly` are too vague by themselves.
- Replace `all the areas that is defined` with a named taxonomy or an explicit note that the taxonomy is still undecided.
- In `spec.md`, define the core entities explicitly: `topic`, `word`, `trend`, `popularity score`, and `time window`.
- Define drill-down behavior. Agents need to know whether a topic click opens a detail page, expands inline, filters the whole dashboard, or updates linked charts.
- Define keyboard accessibility expectations more concretely. For example: all controls reachable by keyboard, visible focus states, and charts paired with tabular summaries.
- Define data-source rules more tightly. `Open and freely available API` is not enough; specify whether scraping is allowed, whether rate limits are acceptable, and whether cached snapshots are allowed.
- Define validation more concretely. `Validated against another source` needs a method: manual spot checks, correlation threshold, or directional agreement.
- In `technology-choices.md`, convert preferences into a single default plus allowed fallback options. Agents work much better with one default than with three parallel options.
- If static hosting is a real constraint, prefer `shiny for python via shinylive` or a pure static frontend over Streamlit.

Questions that would unlock much better agent autonomy:

1. What is the primary source of trend data: news, social media, GitHub, papers, search interest, job postings, or something else?
2. Are topics predefined manually, or should agents derive them from the data?
3. Is the dashboard about individual words only, or about phrases, topics, and entities?
4. What does `popularity` mean here: frequency, growth rate, weighted mentions, search volume, or a composite score?
5. What time granularity should the charts use: daily, weekly, or monthly?
6. How fresh does the data need to be: real-time, daily, weekly, or manually refreshed?
7. Is the dashboard read-only, or should users be able to filter, search, compare, or export?
8. What is the minimum viable topic set for the first release?
9. Which deployment target matters most for the static-site requirement?
10. Should agents treat `streamlit` as disallowed unless you explicitly relax the no-server rule?

My strongest recommendation is to settle three things before deeper scaffolding: the data source, the meaning of popularity, and the default deployment stack. Without those, agents can still build structure, but not the right product.

# Context from my IDE setup:

## Active file: skills/implementation-defaults/agents/openai.yaml

## Open tabs:
- openai.yaml: skills/implementation-defaults/agents/openai.yaml
- SKILL.md: skills/task-decomposition/SKILL.md
- spec.md: spec.md
- prompt.md: prompt.md
- goals.md: goals.md

## My request for Codex:
answers for questions
1. Let's start with social media (mentions and/or hashtag whatever is most easily obtainable), news mentions and Google trends. start by grouping them. with SoMe as top prio, news as second prio and Google trends as 3rd
2. Let's have predefined topics. I'm not sure what these should be but let's start with "prompt engineering", "advanced software production with agents", "general" (words like "vibecoding" that can mean anything today, or company names or model names). 
3. individual words (or several words that describe one concept, for instance : "vibe coding" and "Ralph Wiggum Loop"
4. Good question, let's do social media (mentions and/or hashtag whatever is most easily obtainable), news mentions and Google trends. Individually as frequency and a composite score (the exact formula I don't really know, but let's start with a simple SoMe frequence * SoMe factor + News frequence * News factor + Google trends frequency * Google trends factor) 
5. This should a adjustable. default should be daily
6. Data should be loaded when the dashboard site is loaded and only load new data is required if the user changes filter (or refreshes the browser window).
7. The user should (at least) have the following options: Select a topic to drill down in. User sould be able to Select spatial granularity (days, weeks, months). Use should be able to select a period for the data. User should be able to download the data that is filter to a file in a well described standard format. 
8. The three topics in answer 2 would be sufficient. 
9. I removed the no-server spec. I would like to host on github pages or share.streamlit.io . So stlite, shinylive or wasm technologies or true static site technologies are all allowed (if performance is good) and share.streamlit.io is also completely fine.
10. removed no-server spec fixes this I believe.

Clean up and add these answers to the apopropriate .md and .yml files. Then go through everything again and ask questions if anything is still not reasonable to implement for the agents.

Cleaned up and rewrote `goals.md`, `spec.md`, and `technology-choices.md`, and added `project-context.yml` as a compact machine-readable summary for agents. I removed the template filler, turned your answers into explicit requirements, and set a default implementation direction of `streamlit` on `share.streamlit.io` with static-friendly fallbacks still allowed.

What is still not decision-complete for agents:

1. Which exact social media provider should v1 use first? “Most easily obtainable” still leaves very different implementation paths.
2. Which exact news provider should v1 use first?
3. What initial factor values should the composite score use? If you want a starter default, I suggest `social=0.5`, `news=0.3`, `google_trends=0.2`.
4. What export format should v1 support first? I suggest `csv`.
5. Should agents treat server-side fetching and caching as allowed for the Streamlit path, or should they prefer fully client/static fetching whenever possible?
6. What initial tracked items belong under each of the three topics? Without a seed list, agents can build the shell but not the actual trend coverage.

Once you answer those, the agent work is concrete enough to scaffold the first implementation without guessing on important product decisions.

# Context from my IDE setup:

## Active file: project-context.yml

## Open tabs:
- project-context.yml: project-context.yml
- openai.yaml: skills/implementation-defaults/agents/openai.yaml
- SKILL.md: skills/task-decomposition/SKILL.md
- spec.md: spec.md
- prompt.md: prompt.md

## My request for Codex:
1. Suggest me 4-5 options to choose from. For each option include a rough estimate of number of user and an evaluation of how easily accessibel their API/data is.
2. Suggest me 4-5 options to choose from. For each option include an evaluation of how easily accessibel their API/data is.
3. Sounds good. Make sure it is easy to change later.
4. CSV is fine. But present me with some option for documenting the format so the end user knows how to read and understand the data. 
5. for streamlit using the server and caching is fine. Still "soft" prefer client/static fetching.
6. Look up paper and company blog posts from the major model provider from the last 6 month and based on that present me with some options 


1. Social-media source options

- `Bluesky`
  - Rough size: about `41.4M` users.
  - API/data accessibility: `very high`.
  - Why: Bluesky has open APIs, public endpoints, and a public cached endpoint. This is the easiest clean social source for a v1 trend collector.
- `Reddit`
  - Rough size: about `121M` daily active uniques and `471M` weekly active uniques.
  - API/data accessibility: `medium-high`.
  - Why: very strong topic conversations and keyword coverage. Public/community data is rich, but platform/private-user access is constrained.
- `YouTube`
  - Rough size: `billions` of monthly logged-in users; YouTube also reports `1B+` monthly viewers of podcast content.
  - API/data accessibility: `medium`.
  - Why: official API is good, but you need a project/API key and quota management. Strong for creator/content trend signals, weaker for fast conversational signals than Bluesky or Reddit.
- `LinkedIn`
  - Rough size: about `1.2B` members.
  - API/data accessibility: `low`.
  - Why: huge professional relevance, but most permissions require explicit approval. Better as a later validation/enrichment source than a v1 primary source.

My recommendation for v1:
- Primary: `Bluesky`
- Secondary: `Reddit`
- Optional third social signal: `YouTube`

2. News-source options

- `GDELT`
  - API/data accessibility: `very high`.
  - Why: open, trend-friendly, multilingual, and well suited for keyword-volume timelines. Best default news source for this project.
- `The Guardian Open Platform`
  - API/data accessibility: `high`.
  - Why: clean official API, free non-commercial developer access, article text included, but limited daily quota.
- `NewsAPI`
  - API/data accessibility: `medium`.
  - Why: very easy to use, but the free tier is only for development/testing, has a `24h` delay, and a small daily limit.
- `mediastack`
  - API/data accessibility: `medium-high`.
  - Why: simple REST API, easy onboarding, broad source coverage. Good aggregator option, but still proprietary and free-tier constrained.

My recommendation for v1:
- Primary: `GDELT`
- Secondary validation/backup: `The Guardian`

3. Composite score

Use your proposed starter weights:
- `social=0.5`
- `news=0.3`
- `google_trends=0.2`

Implementation advice:
- keep the factors in one config object or YAML block, not hard-coded across the app
- compute and store both raw source frequencies and the composite score
- make missing-source handling explicit so the formula is easy to revise later

4. Ways to document the CSV format

- `data-dictionary.md` in the repo
  - Best v1 choice.
  - Define every column, units, allowed values, source meaning, and one worked example row.
- In-app `About this data` panel
  - Best for end users.
  - Explain filters, update behavior, score formula, and export columns right next to the dashboard.
- `csvw-metadata.json`
  - Best standards-based option.
  - This follows the W3C CSV on the Web approach and makes the CSV machine-readable as well as human-documented.
- Example export file plus annotated sample
  - Best for quick understanding.
  - Ship one small example CSV and a matching explanation page.

My recommendation for v1:
- `data-dictionary.md` + in-app `About this data`
- add `csvw-metadata.json` later if machine-readable metadata becomes useful

5. Hosting/fetching decision

I would treat this as:
- `Streamlit server + caching`: allowed
- `client/static fetching`: soft preference when it keeps the implementation simpler or cheaper

That is implementable for agents.

6. Tracked-item options based on recent major-provider release themes

This is an inference from recent official posts by OpenAI, Anthropic, and Google. The strongest recurring themes in the last six months are: `coding agents`, `multi-agent workflows`, `computer use`, `deep research`, `reasoning/thinking models`, and `long-running agent tasks`.

Option A: Agentic coding heavy
- `prompt engineering`
  - `system prompt`
  - `tool use`
  - `evals`
  - `structured outputs`
- `advanced software production with agents`
  - `coding agent`
  - `multi-agent`
  - `worktrees`
  - `MCP`
  - `computer use`
  - `background mode`
- `general`
  - `Codex`
  - `Claude Sonnet 4.5`
  - `Gemini 2.5`
  - `Deep Research`

Option B: Research and reasoning heavy
- `prompt engineering`
  - `planning prompt`
  - `retrieval prompt`
  - `evaluation prompt`
- `advanced software production with agents`
  - `reasoning model`
  - `thinking model`
  - `research agent`
  - `long-running task`
  - `tool loop`
- `general`
  - `long context`
  - `1M context`
  - `factuality`
  - `hallucination reduction`

Option C: UI/browser agent heavy
- `prompt engineering`
  - `stop condition`
  - `retry loop`
  - `browser tool prompt`
- `advanced software production with agents`
  - `computer use`
  - `browser agent`
  - `UI automation`
  - `tool-calling`
  - `agent loop`
- `general`
  - `Gemini Computer Use`
  - `Claude computer use`
  - `autonomous agent`

My recommendation for v1:
- choose `Option A`
- then borrow `computer use` from Option C
- and keep provider/model names in `general`

That gives you a seed list that matches the current market language without being too broad.

What I still need from you to make this fully implementation-ready:

1. Pick one primary social source for v1: `Bluesky`, `Reddit`, or `YouTube`.
2. Pick one primary news source for v1: `GDELT`, `Guardian`, `NewsAPI`, or `mediastack`.
3. Pick one tracked-item option: `A`, `B`, `C`, or a hybrid.

Sources:
- Bluesky users and public API docs: https://bsky.social/about/blog/01-29-2026-transparency-report-2025 , https://docs.bsky.app/docs/advanced-guides/api-directory
- Reddit scale and API docs: https://investor.redditinc.com/overview/default.aspx , https://developers.reddit.com/docs/capabilities/server/reddit-api
- YouTube API and scale references: https://developers.google.com/youtube/v3/getting-started , https://blog.youtube/press , https://blog.youtube/news-and-events/1-billion-monthly-podcast-users/
- LinkedIn scale and API access rules: https://news.linkedin.com/2025/Q4FY25_Earnings_Highlights , https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- Guardian Open Platform: https://open-platform.theguardian.com/ , https://open-platform.theguardian.com/access/
- NewsAPI pricing/access: https://newsapi.org/pricing
- mediastack docs: https://mediastack.com/documentation
- OpenAI recent agent/coding themes: https://openai.com/index/introducing-codex/ , https://openai.com/index/introducing-the-codex-app/
- Anthropic recent agent/coding themes: https://www.anthropic.com/news/claude-sonnet-4-5
- Google recent agent/research/computer-use themes: https://blog.google/innovation-and-ai/technology/developers-tools/interactions-api/ , https://blog.google/innovation-and-ai/technology/developers-tools/deep-research-agent-gemini-api/ , https://blog.google/innovation-and-ai/models-and-research/google-deepmind/gemini-computer-use-model/

# Context from my IDE setup:

## Open tabs:
- project-context.yml: project-context.yml
- openai.yaml: skills/implementation-defaults/agents/openai.yaml
- SKILL.md: skills/task-decomposition/SKILL.md
- spec.md: spec.md
- prompt.md: prompt.md

## My request for Codex:
1. Let's go with Bluesky (add a reminder to check out Mastodon at a later point)
2. Let's go with GDELT (add a reminder to check out Hackernews at a later point)
4. Let's go with a data-dictionary.md . In the UI also make data-dictionary.md downloadable.
6. Let's go with option A (no hybrid)

Updated the project docs with your choices: `Bluesky` is now the selected social source, `GDELT` is the selected news source, `CSV` is the default export format, `data-dictionary.md` has been added and marked as downloadable from the UI, and tracked-item seed option `A` is now the selected starting point. I also added deferred reminders for `Mastodon` and `Hacker News`, and captured the fetching preference that Streamlit server-side fetching and caching are allowed while client/static fetching remains a soft preference.

I found and fixed one leftover inconsistency during the review: `goals.md` still had export format listed as an open question even though `CSV` was already chosen.

What is still not fully specified enough for agents to implement without guessing:

1. Composite weights: are you happy with `social=0.5`, `news=0.3`, `google_trends=0.2` as the initial values?
2. Seed list contents: for option `A`, which exact tracked items should be included under each of the three topics?
3. Partial-source behavior: if one data source fails, should the app recompute the composite score from the remaining sources, or should it keep the original formula and show a partial-data warning?

After those three decisions, the project is concrete enough for agents to scaffold the first implementation without important product guesses.

# Context from my IDE setup:

## Active file: technology-choices.md

## Open tabs:
- technology-choices.md: technology-choices.md
- spec.md: spec.md
- prompt.md: prompt.md
- project-context.yml: project-context.yml
- goals.md: goals.md

## My request for Codex:
1. yes
2. this (but make it easy to chance, in the future it might need to be evaluated dynamically):
* prompt engineering 
  - system prompt 
  - tool use 
  - evals 
  - structured outputs 
* advanced software production with agents 
  - coding agent 
  - multi-agent 
  - worktrees 
  - MCP 
  - computer use 
  - background mode 
* general 
  - Codex 
  - Claude Sonnet 
  - Gemini 
  - Deep Research
3. Keep remaining and warn.

Applied the remaining decisions. The composite weights are now fixed at `0.5 / 0.3 / 0.2`, partial-source failures now resolve to `warn and keep remaining data`, and the tracked-item seed list has been moved into a dedicated `tracked-items.yml` file so it stays easy to edit now and easier to evaluate dynamically later. I also updated the project docs so they point to that file instead of keeping the seed list buried in prose.

At this point only one meaningful product question is still open: how to handle topic membership when a term could plausibly belong to more than one topic. Everything else is now specific enough for agents to start scaffolding the first implementation without making product guesses.

# Context from my IDE setup:

## Active file: technology-choices.md

## Open tabs:
- technology-choices.md: technology-choices.md
- spec.md: spec.md
- prompt.md: prompt.md
- project-context.yml: project-context.yml
- goals.md: goals.md

## My request for Codex:
Right now just add to both topics. In real life topics overlap anywa.

Updated the project docs to allow overlapping topic membership. For the current version, if a tracked item fits more than one topic, agents should include it in each relevant topic rather than forcing a single assignment.

That closes the last open product rule. The project docs are now specific enough for agents to scaffold the first implementation without material product guessing.

# Context from my IDE setup:

## Active file: technology-choices.md

## Open tabs:
- technology-choices.md: technology-choices.md
- spec.md: spec.md
- prompt.md: prompt.md
- project-context.yml: project-context.yml
- goals.md: goals.md

## My request for Codex:
Ok, is there anything else to be done before implementing? Otherwise please go ahead.

There was nothing product-critical left to decide, so I went ahead and scaffolded the first implementation. The repo now has a Streamlit app in `app.py`, config/data helpers in `genai_trends/`, a dependency file in `requirements.txt`, and an updated `data-dictionary.md` that matches the CSV export schema. The app reads `project-context.yml` and `tracked-items.yml`, shows topic and tracked-item trend charts, supports CSV export for the filtered view, and makes `data-dictionary.md` downloadable from the UI.

The current data layer is intentionally a deterministic sample-data scaffold, not live Bluesky/GDELT/Google Trends integration yet. That keeps the UI, config model, export shape, and failure-handling rules in place while leaving the collectors easy to swap in next. I was not able to run the app or automated checks here because Python execution is blocked in this environment, and `git status` is also blocked by the repository ownership safety check, so verification was a manual code pass only.

# Context from my IDE setup:

## Active file: app.py

## Open tabs:
- app.py: app.py
- launch.json: .vscode/launch.json
- SKILL.md: skills/task-decomposition/SKILL.md
- SKILL.md: skills/implementation-defaults/SKILL.md
- requirements.txt: requirements.txt

## My request for Codex:
add a appropriate .gitignore file

Added a root `.gitignore` with sensible defaults for this Python/Streamlit project, including Python caches, virtual environments, build artifacts, local Streamlit secrets, OS/editor noise, and temp files. I also kept `.vscode/launch.json` tracked while ignoring other `.vscode` files.
