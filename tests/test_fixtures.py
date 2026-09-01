"""End-to-end regression suite against real Maven fixtures (REQUIREMENTS_1.md §11).

Each fixtures/<name>/ holds base/ and head/ project trees plus expected.json. The harness
builds a throwaway git repo (base commit, then head commit) and runs greenwash in
single-commit mode with the default Maven build command. Green on every commit. Requires
Maven on PATH; skipped with a clear message when absent (run in CI — see
.github/workflows/ci.yml). The hermetic equivalent is tests/test_orchestrate.py.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from greenwash.config import Config
from greenwash.orchestrate import Options, verify
from greenwash.output import _finding_subject

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _fixture_dirs():
    if not FIXTURES.is_dir():
        return []
    return sorted(d for d in FIXTURES.iterdir() if (d / "expected.json").is_file())


@unittest.skipUnless(shutil.which("mvn"), "Maven not on PATH")
class FixtureRegressionTest(unittest.TestCase):
    pass


def _make_case(fixture: Path):
    def test(self):
        expected = json.loads((fixture / "expected.json").read_text())
        work = Path(tempfile.mkdtemp(prefix=f"gw-fx-{fixture.name}-"))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)

        def git(*args):
            proc = subprocess.run(
                ["git", "-C", str(work), *args], capture_output=True, text=True
            )
            if proc.returncode != 0:
                self.fail(f"git {' '.join(args)} -> {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
            return proc.stdout

        def load_tree(side):
            for entry in list(os.listdir(work)):
                if entry == ".git":
                    continue
                path = work / entry
                shutil.rmtree(path) if path.is_dir() else path.unlink()
            shutil.copytree(fixture / side, work, dirs_exist_ok=True)

        load_tree("base")
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("add", "-A")
        git("commit", "-qm", "base")

        load_tree("head")
        git("add", "-A")
        git("commit", "-qm", "head", "--allow-empty")  # --allow-empty: surface a bad
        sha = git("rev-parse", "HEAD").strip()          # tree as an assertion, not a crash

        diff_stat = git("diff", "--stat", f"{sha}~1", sha).strip()
        if not diff_stat and expected["headline_verdict"] != "NO_TEST_CHANGES":
            tree = git("ls-tree", "-r", "--name-only", sha).strip()
            tf = work / "src/test/java/calc/CalculatorTest.java"
            body = tf.read_text() if tf.exists() else "<missing>"
            src_head = (fixture / "head/src/test/java/calc/CalculatorTest.java")
            self.fail(
                f"empty base->head diff for {fixture.name}\n"
                f"worktree tree:\n{tree}\n\nworktree CalculatorTest.java:\n{body}\n"
                f"fixture head file exists: {src_head.exists()}; "
                f"content:\n{src_head.read_text() if src_head.exists() else '<missing>'}"
            )

        report = verify(Options(repo_root=str(work), commit=sha), Config())

        self.assertEqual(report.headline.value, expected["headline_verdict"])
        got = sorted((f.verdict.value, f.module, _finding_subject(f)) for f in report.findings)
        want = sorted((e["verdict"], e["module"], e["subject"]) for e in expected["findings"])
        self.assertEqual(got, want)

    return test


for _d in _fixture_dirs():
    setattr(FixtureRegressionTest, f"test_{_d.name.replace('-', '_')}", _make_case(_d))


if __name__ == "__main__":
    unittest.main()
