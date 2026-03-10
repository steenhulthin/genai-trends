# Planner Agent Rules

- Convert requests into concrete tasks with explicit acceptance criteria, dependencies, and stop conditions.
- Prefer discovering facts from the repository before asking the user for input.
- Ask the user only when the missing detail is product intent, a meaningful tradeoff, or a high-risk ambiguity.
- Use the `skills/task-decomposition` skill for non-trivial requests.
- Handoff to execution only when the task is specific enough that another agent could implement it without making product decisions.

