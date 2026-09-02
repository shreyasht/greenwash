"""Static strictness analysis of test/config changes.

Two consumers, both governed by §4.1 — "pattern matching may decide *when* to run the
experiment; it must never *be* the finding":

  1. Pre-filter (§8 v0.3): when opted in, skip the replay entirely if none of the
     test/config changes show a strictness reduction.
  2. Compile-wall fallback (§9): when the base tests will not compile against the new
     source, enrich the otherwise-useless INCONCLUSIVE_COMPILE result with the *suspected*
     weakenings — clearly labelled as heuristic, not verified by replay.

Deliberately conservative: the absence of a signal is not proof that a change is
strengthening, only that there is no visible evidence of weakening. Only recognised JVM
test sources and common config shapes are analysed; anything else never clears the
pre-filter.
"""

from __future__ import annotations

import re

_JVM_TEST_EXT = (".java", ".kt", ".kts", ".groovy", ".scala")

_DISABLE_ADDED = re.compile(
    r"@Disabled\b|@Ignore\b|assumeTrue\s*\(\s*false|assumeFalse\s*\(\s*true|"
    r"@Test\s*\([^)]*enabled\s*=\s*false|@Test\s*\([^)]*disabled",
)
_ASSERT_LINE = re.compile(
    r"\bassert[A-Za-z]*\s*\(|\bassertThat\b|\bverify\s*\(|\bfail\s*\(|"
    r"\bexpectThrows\b|\bassertThrows\b|\bshould\b",
)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_CONFIG_BLOCK = re.compile(r"</?(rule|plugin|execution|enforce|check|limit|coveralls)\b", re.I)
_CONFIG_SKIP_ADDED = re.compile(
    r"skip\s*[>=]\s*[\"']?true|failOnError\s*[>=]\s*[\"']?false|maven\.test\.skip|"
    r"ignoreFailures\s*=\s*true|-x\s+\w*[Cc]heck|continue-on-error\s*:\s*true",
)


def _added(diff: str) -> list[str]:
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def _removed(diff: str) -> list[str]:
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")]


def _digits_masked(s: str) -> str:
    return _NUMBER.sub("#", s).strip()


def _jvm_test_signals(added: list[str], removed: list[str]) -> list[str]:
    reasons: list[str] = []
    if any(_DISABLE_ADDED.search(a) for a in added):
        reasons.append("a test was disabled or its assumption was made to fail")

    removed_asserts = sum(1 for r in removed if _ASSERT_LINE.search(r))
    added_asserts = sum(1 for a in added if _ASSERT_LINE.search(a))
    if removed_asserts > added_asserts:
        reasons.append(f"{removed_asserts - added_asserts} more assertion line(s) removed than added")

    if any("@Test" in r for r in removed) and not any("@Test" in a for a in added):
        reasons.append("a @Test method was removed")

    removed_eq = {r.strip() for r in removed if "assertEquals" in r or "assertThat" in r}
    added_eq = {a.strip() for a in added if "assertEquals" in a or "assertThat" in a}
    if removed_eq and added_eq and removed_eq != added_eq:
        reasons.append("an assertion's expected value changed")
    return reasons


def _config_signals(added: list[str], removed: list[str]) -> list[str]:
    reasons: list[str] = []
    if any(_CONFIG_BLOCK.search(r) for r in removed) and not any(_CONFIG_BLOCK.search(a) for a in added):
        reasons.append("a rule / plugin / execution / limit block was removed")
    if any(_CONFIG_SKIP_ADDED.search(a) for a in added):
        reasons.append("a skip / ignore-failure / continue-on-error flag was added")
    for r in removed:
        for a in added:
            rn, an = _NUMBER.findall(r), _NUMBER.findall(a)
            if rn and an and _digits_masked(r) == _digits_masked(a):
                if any(float(x) > float(y) for x, y in zip(rn, an)):
                    reasons.append("a numeric threshold decreased")
                    return reasons
    return reasons


def _analysable(path: str, kind: str) -> bool:
    return kind == "config" or (kind == "test" and path.endswith(_JVM_TEST_EXT))


def weakening_signals(path: str, kind: str, diff: str) -> list[str]:
    """Concrete weakening signals in one file's diff. Empty for a file with none, and
    empty for a file astroturf cannot statically read (use `unrecognised` to tell the
    two apart)."""
    added, removed = _added(diff), _removed(diff)
    if kind == "test" and path.endswith(_JVM_TEST_EXT):
        return _jvm_test_signals(added, removed)
    if kind == "config":
        return _config_signals(added, removed)
    return []


def analyse(items: list[tuple[str, str, str]]) -> dict:
    """`items` are (path, kind, diff_text). Returns:
    - signals: {path: [weakening reasons]} — the concrete evidence
    - weakened_paths: sorted keys of signals
    - unrecognised: paths that could not be statically analysed at all
    The pre-filter may skip the replay only when weakened_paths AND unrecognised are both
    empty (§4.1 — never skip on an unread file)."""
    signals = {
        path: reasons
        for path, kind, diff in items
        if (reasons := weakening_signals(path, kind, diff))
    }
    unrecognised = sorted(
        path for path, kind, _ in items if path not in signals and not _analysable(path, kind)
    )
    return {
        "signals": signals,
        "weakened_paths": sorted(signals),
        "unrecognised": unrecognised,
    }
