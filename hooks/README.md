# Integration surfaces (REQUIREMENTS_1.md §10, FR-35, FR-36)

Ascending in value:

1. `github-actions/` — CI check on PRs. Lowest value; the change already landed.
2. `pre-commit` — catches a hacked test before it enters history.
3. `claude-stop-hook/` — **the differentiating integration.** greenwash runs inside the
   agent's completion loop; on a blocking verdict the agent is stopped and handed the
   reason, and retries with no human in the loop.

All three must respect NFR-4: a broken hook never blocks a build or traps an agent.

Status: stubs. Built at `BUILD_PLAN.md` §3 steps 11–12.
