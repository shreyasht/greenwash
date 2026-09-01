"""End-to-end split-and-replay through orchestrate.verify(), hermetic.

Uses a stdlib fake build (`python3 runtests.py`) instead of Maven so every verdict is
exercised on any machine with no JVM and no network. The real Maven integration lives in
tests/test_fixtures.py.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from greenwash import cli
from greenwash.config import Config
from greenwash.orchestrate import Options, verify
from greenwash.output import _finding_subject
from greenwash.verdict import Verdict

RUNTESTS = '''import json, os
os.makedirs("target/surefire-reports", exist_ok=True)
ns = {}
exec(open("calc.py").read(), ns)
# A case marked "flaky" passes only on the very first build across the whole run
# (tracked in the file named by GW_FLAKY_COUNTER), so flake confirmation demotes it.
counter = os.environ.get("GW_FLAKY_COUNTER")
first_build = True
if counter:
    first_build = not os.path.exists(counter)
    open(counter, "a").write("x")
rows = []
for c in json.load(open("cases.json")):
    if c.get("flaky"):
        ok = first_build
    else:
        ok = ns["add"](c["a"], c["b"]) == c["expected"]
    tag = "" if ok else '<failure message="x"/>'
    rows.append('<testcase name="' + c["name"] + '" classname="calc.CalcTest">' + tag + '</testcase>')
xml = '<?xml version="1.0"?>\\n<testsuite name="calc.CalcTest">\\n' + "\\n".join(rows) + '\\n</testsuite>\\n'
open("target/surefire-reports/TEST-calc.CalcTest.xml", "w").write(xml)
'''

BUG = "def add(a, b):\n    return a\n"
FIX = "def add(a, b):\n    return a + b\n"
ONE = json.dumps([{"name": "addsTwoNumbers", "a": 2, "b": 3, "expected": 5}])
ONE_HACKED = json.dumps([{"name": "addsTwoNumbers", "a": 2, "b": 3, "expected": 2}])
TWO = json.dumps([
    {"name": "addsTwoNumbers", "a": 2, "b": 3, "expected": 5},
    {"name": "addsZero", "a": 0, "b": 0, "expected": 0},
])

BUILD_CMD = ["python3", "runtests.py"]
OVERRIDES = {"calc.py": "source", "cases.json": "test"}


class OrchestrateTest(unittest.TestCase):
    def _repo(self, base_files, head_files):
        d = Path(tempfile.mkdtemp(prefix="greenwash-e2e-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)

        def git(*a):
            subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        for name, content in base_files.items():
            (d / name).write_text(content)
        git("add", "-A")
        git("commit", "-qm", "base")
        for name in base_files:
            if name not in head_files:
                (d / name).unlink()
        for name, content in head_files.items():
            (d / name).write_text(content)
        git("add", "-A")
        git("commit", "-qm", "head")
        head_sha = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        return str(d), head_sha

    def _verify(self, base, head):
        root, sha = self._repo(base, head)
        cfg = Config(build_command=BUILD_CMD, classification_overrides=OVERRIDES)
        return verify(Options(repo_root=root, commit=sha), cfg)

    def _b(self, calc, cases):
        return {"runtests.py": RUNTESTS, "calc.py": calc, "cases.json": cases}

    def test_honest_fix(self):
        r = self._verify(self._b(BUG, ONE), self._b(FIX, TWO))
        self.assertEqual(r.headline, Verdict.HONEST_FIX)
        self.assertEqual(r.findings, [])

    def test_fix_is_in_the_tests(self):
        r = self._verify(self._b(BUG, ONE), self._b(BUG, ONE_HACKED))
        self.assertEqual(r.headline, Verdict.FIX_IS_IN_THE_TESTS)
        self.assertIn("calc.CalcTest.addsTwoNumbers", [_finding_subject(f) for f in r.findings])

    def test_tests_removed(self):
        r = self._verify(self._b(BUG, TWO), self._b(FIX, ONE))
        self.assertEqual(r.headline, Verdict.TESTS_REMOVED_OR_SKIPPED)
        self.assertIn("calc.CalcTest.addsZero", [_finding_subject(f) for f in r.findings])

    def test_no_test_changes_skips_replay(self):
        r = self._verify(self._b(BUG, ONE), self._b(FIX, ONE))
        self.assertEqual(r.headline, Verdict.NO_TEST_CHANGES)

    def test_fix_in_tests_survives_flake_confirmation(self):
        # deterministic fake build -> the FIX_IS_IN_THE_TESTS candidate is re-confirmed
        r = self._verify(self._b(BUG, ONE), self._b(BUG, ONE_HACKED))
        self.assertEqual(r.headline, Verdict.FIX_IS_IN_THE_TESTS)
        self.assertTrue(any("isolation" in w for w in r.warnings))  # FR-29 caveat

    def test_flaky_candidate_is_demoted(self):
        counter_dir = tempfile.mkdtemp(prefix="gw-flaky-")
        self.addCleanup(shutil.rmtree, counter_dir, ignore_errors=True)
        os.environ["GW_FLAKY_COUNTER"] = os.path.join(counter_dir, "c")
        flaky_case = json.dumps(
            [{"name": "addsTwoNumbers", "a": 2, "b": 3, "expected": 5, "flaky": True}]
        )
        try:
            r = self._verify(self._b(BUG, ONE), self._b(BUG, flaky_case))
        finally:
            os.environ.pop("GW_FLAKY_COUNTER", None)
        self.assertEqual(r.headline, Verdict.INCONCLUSIVE_FLAKY)

    def test_nondestructive_and_no_leftover_worktrees(self):
        root, sha = self._repo(self._b(BUG, ONE), self._b(BUG, ONE_HACKED))

        def g(*a):
            return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True).stdout

        before = (g("status", "--porcelain"), g("stash", "list"), g("rev-parse", "HEAD"))
        verify(Options(repo_root=root, commit=sha),
               Config(build_command=BUILD_CMD, classification_overrides=OVERRIDES))
        after = (g("status", "--porcelain"), g("stash", "list"), g("rev-parse", "HEAD"))
        self.assertEqual(before, after)
        self.assertEqual(g("worktree", "list").strip().count("\n"), 0)

    def test_cli_exit_code_and_json(self):
        toml = (
            'build_command = ["python3", "runtests.py"]\n'
            "[classification_overrides]\n"
            '"calc.py" = "source"\n'
            '"cases.json" = "test"\n'
        )
        base = {**self._b(BUG, ONE), ".greenwash.toml": toml}
        head = {**self._b(BUG, ONE_HACKED), ".greenwash.toml": toml}
        root, sha = self._repo(base, head)

        old = os.getcwd()
        os.chdir(root)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = cli.main(["--commit", sha, "--json"])
        finally:
            os.chdir(old)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(buf.getvalue())["headline_verdict"], "FIX_IS_IN_THE_TESTS")


if __name__ == "__main__":
    unittest.main()
