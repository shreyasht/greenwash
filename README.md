# 🧽 greenwash

**Deterministic verification for AI coding agents. Did it fix the source, or just hack the tests?**

Coding agents are measured by the checks they can pass. When an agent cannot make a test pass, a cheaper path is often available: **make the test stop asking.** 

In benchmarks and real-world usage, agents (like Codex and Claude Code) have been observed explicitly reward-hacking—hardcoding expected values, deleting assertions, and lowering coverage thresholds to report a "green" build.

Code review doesn't close this trust gap because reviewers read diffs for correctness, not to determine if a test edit is artificially propping up a broken fix.

**greenwash** answers one question deterministically:
> **Does the source change, on its own, still satisfy the checks?**

## 🔬 How it Works: Split and Replay

greenwash answers by experiment, not inference. It uses no LLMs in its verification path. 

When analyzing a diff, it splits the changes into three buckets: `source`, `test`, and `config`. It then runs the build in two states and compares the outcomes:

1. **Run A ("After"):** All hunks applied (the proposed PR).
2. **Run B ("Source-only"):** Test and config changes reverted to base.

```text
                 ┌── source hunks ──┐
   diff ─────────┼── test hunks ────┼──► run A ("after"):       all hunks applied
                 └── config hunks ──┘
                                     └──► run B ("source-only"): test + config reverted to base
```

If a test passes in **Run A** but fails in **Run B**, it is not evidence of a fix. It is evidence of a moved goalpost.

## ⚖️ Findings and Verdicts

greenwash evaluates two observables: **per-test outcomes** (to catch weakened assertions) and **gate outcomes** (to catch lowered coverage or disabled linters). 

It emits a list of findings and a single **headline verdict**:

| Verdict | Meaning | Action |
| --- | --- | --- |
| 🛑 `FIX_IS_IN_THE_TESTS` | Source change alone does not make the named tests pass. | **Blocks Build** |
| 🛑 `CONFIG_WEAKENED` | A gate (e.g. coverage) that failed at base now passes. | **Blocks Build** |
| ⚠️ `TESTS_REMOVED_OR_SKIPPED` | Source fix holds, but coverage shrank. | Informs |
| ✅ `HONEST_FIX` | Tests/config changed, and the source fix holds without them. | Passes |
| ⏩ `NO_TEST_CHANGES` | No test or config files touched; nothing to verify. | Passes |

*Note: greenwash employs automatic flake confirmation to ensure verdicts are highly reliable.*

## 🔌 Integrations

greenwash is designed to run where it matters most:

1. **Agent Stop Hook (The Killer Feature):** Plugs directly into agents (like Claude Code) to intercept success reports. The agent is blocked and handed the verdict: *"your fix is in the test file."* It is forced to retry with no human in the loop.
2. **Pre-commit Hook:** Catches hacked tests before they enter your local history.
3. **CI/CD Action:** A standard GitHub Action to protect the `main` branch.

## 🛡️ Design Principles

* **Deterministic Core:** No LLMs in the verification path. Same inputs = same verdict.
* **No Egress:** Source code never leaves your machine. No telemetry, API keys, or network calls. Safe for enterprise environments.
* **Zero Install Friction:** Python stdlib only. No JVM plugins, no build-file modification.
* **Non-destructive:** Uses isolated git worktrees. Your working directory is never mutated.
* **Fail Open:** On internal ambiguity (e.g. compile failures), it exits `0` so it never blocks a valid build unnecessarily. 

## 🚀 Getting Started

*(Coming soon: Installation instructions for v0.3)*
