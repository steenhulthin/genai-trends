---
name: implementation-defaults
description: Provide execution defaults for agent-driven implementation work. Use when an executor agent should act directly, choose a safe order of operations, verify results locally, and avoid pushing mechanical steps back to the user.
---

# Implementation Defaults

Execute directly unless a real blocker exists.

## Workflow

1. Confirm the active task and acceptance criteria.
2. Inspect the minimum relevant files before editing.
3. Make the smallest coherent change that completes the task.
4. Run the narrowest useful local verification available.
5. Summarize the result, validation, and any remaining risks concisely.

## Escalate Only For

- Destructive actions the user did not request
- Missing permissions
- Missing product intent
- Conflicting requirements
- Verification failures that cannot be repaired safely

## Reporting Defaults

- Lead with outcome, not process.
- Mention only the verification actually performed.
- Avoid giving the user a manual checklist when the agent can do the work itself.

