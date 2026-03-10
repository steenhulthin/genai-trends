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
