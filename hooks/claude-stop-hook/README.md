# Claude Code Stop hook (FR-36)

A `Stop` hook that runs greenwash on the working-tree diff when the agent tries to end its
turn.

- Blocking verdict (`FIX_IS_IN_THE_TESTS`, `CONFIG_WEAKENED`): the hook blocks the stop
  and returns the verdict text to the agent (e.g. *"your fix is in the test file"*), so it
  self-corrects before reporting success.
- Anything else: silent, agent proceeds.
- Fail open (NFR-4): any error in the hook lets the agent stop normally.

To be implemented at `BUILD_PLAN.md` §3 step 12. Ship as a documented
`settings.json` hook snippet plus the wrapper script it calls.
