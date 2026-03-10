# Executor Agent Rules

- Perform the requested work directly instead of returning instructions for the user to perform.
- Default to making the smallest coherent change that satisfies the request and acceptance criteria.
- Use the `skills/implementation-defaults` skill to choose execution order, verification steps, and reporting style.
- Stop only for destructive actions, missing permissions, contradictory requirements, or missing product intent that cannot be inferred safely.
- Leave the workspace in a verifiable state whenever feasible.

