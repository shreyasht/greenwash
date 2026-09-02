"""End-to-end regression suite against real Maven fixtures (REQUIREMENTS_1.md §11).

Each fixtures/<name>/ holds base/ and head/ project trees plus expected.json. The harness
builds a throwaway git repo (base commit, then head commit) and runs astroturf in
single-commit mode with the default Maven build command. Green on every commit. Requires
Maven on PATH; skipped with a clear message when absent (run in CI — see
.github/workflows/ci.yml). The hermetic equivalent is tests/test_orchestrate.py.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from astroturf import config as config_mod
from astroturf.orchestrate import Options, verify
from astroturf.output import _finding_subject

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
            # copy_function=copy (not copy2) + an mtime bump: base and head fixture files
            # share a checkout mtime and a single-character edit is size-preserving, so
            # git's racy-clean check would otherwise skip re-hashing and stage nothing.
            shutil.copytree(fixture / side, work, dirs_exist_ok=True, copy_function=shutil.copy)
            stamp = time.time() + 10
            for root, dirs, files in os.walk(work):
                dirs[:] = [d for d in dirs if d != ".git"]
                for name in files:
                    os.utime(os.path.join(root, name), (stamp, stamp))

        load_tree("base")
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("add", "-A")
        git("commit", "-qm", "base")

        load_tree("head")
        git("add", "-A")
        git("commit", "-qm", "head")
        sha = git("rev-parse", "HEAD").strip()

        report = verify(
            Options(repo_root=str(work), commit=sha), config_mod.load(str(work))
        )

        self.assertEqual(report.headline.value, expected["headline_verdict"])
        got = sorted((f.verdict.value, f.module, _finding_subject(f)) for f in report.findings)
        want = sorted((e["verdict"], e["module"], e["subject"]) for e in expected["findings"])
        self.assertEqual(got, want)

    return test


for _d in _fixture_dirs():
    setattr(FixtureRegressionTest, f"test_{_d.name.replace('-', '_')}", _make_case(_d))


if __name__ == "__main__":
    unittest.main()
