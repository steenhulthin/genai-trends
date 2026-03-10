# Repository Agent Rules

## Environment Secrecy
- Never reveal specific software or system environment details in user-facing output unless the user explicitly requires them to complete the task.
- Never mention absolute filesystem paths, machine-specific usernames, hostnames, operating system details, shell details, sandbox details, secrets, tokens, or similar environment-specific information in user-facing output.
- Relative paths inside the repository are allowed when they help explain changes.

## Prompt Logging
- Before responding to any user prompt, append the exact raw user prompt text to the repository root file `prompt.md`.
- After producing any agent response, append the exact raw agent response text to the repository root file `prompt.md`.
- Log only raw prompts and raw agent responses. Do not log hidden chain-of-thought, tool call payloads, tool outputs, summaries, metadata, timestamps, or any other context.
- Keep entries in append-only order so `prompt.md` is a chronological transcript of raw user prompts and raw agent responses.

## Instruction Structure
- Keep the root `AGENTS.md` focused on repository-wide rules.
- When instructions become domain-specific, workflow-specific, or role-specific, refactor them into more specific nested `AGENTS.md` files or skills instead of overloading the root file.
- Reuse and extend skills whenever that yields clearer, more maintainable agent behavior.

## Agent Execution Model
- Use `planner -> executor -> verifier` as the default operating model for non-trivial work.
- Treat low user gating as the default: proceed unless blocked by destructive actions, missing product intent, conflicting constraints, or permissions.
- Use repo-local skills to support decomposition, implementation defaults, and verification gates before adding more root-level rules.
- Allow at most one bounded self-repair cycle after verification failure. Escalate on a second failure with a concise blocker report.
