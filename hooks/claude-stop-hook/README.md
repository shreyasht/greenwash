# Claude Code Stop hook (FR-36)

The differentiating integration (§10 surface 3): astroturf runs inside the agent's
completion loop. On `FIX_IS_IN_THE_TESTS` or `CONFIG_WEAKENED` the agent is blocked from
ending its turn and handed the verdict, so it retries with no human involved.

## Install

```
pip install "git+https://github.com/shreyasht/astroturf@main"
```

This provides the `astroturf-stop-hook` command. Add it to the guarded project's
`.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "astroturf-stop-hook" } ] }
    ]
  }
}
```

## Behaviour

- Reads the Stop-hook JSON on stdin, runs `astroturf --json` in the agent's `cwd`.
- Blocking verdict → prints `{"decision": "block", "reason": "..."}` and exits 0; Claude
  Code shows `reason` to the agent and it keeps working.
- Any other verdict, a astroturf error, or `stop_hook_active` already set → exits 0
  silently and the agent stops (NFR-4 fail open; never blocks twice in a turn).
- `ASTROTURF_HOOK_TIMEOUT` (seconds, default 1800) caps the two build runs.

The decision logic is `astroturf.stophook.evaluate`; this directory only documents it.
