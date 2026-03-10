---
name: task-decomposition
description: Break a user request into concrete executable tasks with acceptance criteria, dependencies, and stop conditions. Use when planning non-trivial implementation work, when deciding whether agents can proceed without asking the user, or when handing work from a planner agent to an executor agent.
---

# Task Decomposition

Turn a request into a short execution spec that another agent can implement without making product decisions.

## Workflow

1. Restate the task in one sentence using the user's intent, not internal process language.
2. List the smallest meaningful work units required to complete the task.
3. Attach acceptance criteria to each work unit when the criteria are not already obvious.
4. Call out dependencies, required discoveries, or blockers that must be resolved before execution.
5. Define stop conditions so the executor knows when to ask instead of guessing.

## Defaults

- Prefer 3 to 7 work units.
- Keep each unit implementation-oriented.
- Treat missing product intent as a blocker.
- Treat discoverable repository facts as work for the planner, not a question for the user.

## Handoff Format

- Goal
- Work units
- Acceptance criteria
- Dependencies
- Stop conditions

