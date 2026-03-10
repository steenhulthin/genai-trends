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
