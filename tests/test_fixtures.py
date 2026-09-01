"""End-to-end regression suite against real Maven fixtures (REQUIREMENTS_1.md §11).

Each fixtures/<name>/ holds base/ and head/ project trees plus expected.json. The harness
builds a throwaway git repo (base commit, then head commit) and runs greenwash in
single-commit mode with the default Maven build command. Green on every commit. Requires
Maven on PATH; skipped with a clear message when absent (run in CI — see
.github/workflows/ci.yml). The hermetic equivalent is tests/test_orchestrate.py.
"""

import json
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
            subprocess.run(["git", "-C", str(work), *args], check=True, capture_output=True)

        shutil.copytree(fixture / "base", work, dirs_exist_ok=True)
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("add", "-A")
        git("commit", "-qm", "base")

        for p in work.iterdir():
            if p.name == ".git":
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        shutil.copytree(fixture / "head", work, dirs_exist_ok=True)
        git("add", "-A")
        git("commit", "-qm", "head")
        sha = subprocess.run(
            ["git", "-C", str(work), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()

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
