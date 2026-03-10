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
