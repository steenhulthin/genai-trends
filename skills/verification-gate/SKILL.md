---
name: verification-gate
description: Verify whether agent output meets acceptance criteria and decide whether to accept, trigger one bounded repair cycle, or escalate. Use when a verifier agent needs a consistent rule for retries, regression checks, and blocker reporting.
---

# Verification Gate

Apply a bounded acceptance decision after execution.

## Decision Order

1. Check whether the stated acceptance criteria are satisfied.
2. Check for obvious regressions in nearby behavior.
3. Run the narrowest reliable validation available.
4. Decide `accept`, `retry-once`, or `escalate`.

## Retry Once

Choose `retry-once` only when all of the following are true:

- The failure is specific and fixable.
- No new product decision is required.
- The retry can be scoped narrowly.
- A second pass is likely to succeed.

## Escalate

Escalate immediately when:

- Acceptance criteria are missing or contradictory.
- A destructive or permission-gated step blocks verification.
- Required dependencies are unavailable.
- The first repair attempt fails.

## Output Format

- Decision
- Evidence
- Repair target, if retrying
- Blocker, if escalating

