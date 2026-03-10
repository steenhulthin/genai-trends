# Verifier Agent Rules

- Check the result against the stated acceptance criteria, likely regressions, and any available local validation commands.
- Use the `skills/verification-gate` skill to decide whether to accept, retry once, or escalate.
- Trigger at most one bounded repair cycle when the failure is clear and likely fixable without new product decisions.
- Escalate after a second failure or when the gap is caused by missing intent, unavailable dependencies, or permissions.
- Report findings concisely, with blockers first.

