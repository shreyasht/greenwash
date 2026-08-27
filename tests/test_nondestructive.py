"""NFR-5 property test: a greenwash run leaves the repo's working tree, index, and stash
list byte-identical. This is the foundation everything else trusts (BUILD_PLAN.md §3
step 1) and must stay green for the life of the project.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from greenwash import revisions


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    ).stdout


class NonDestructiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="greenwash-test-")
        self.repo = Path(self.tmp)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.txt").write_text("one\n")
        (self.repo / "b.txt").write_text("keep\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")

        # a pre-existing stash entry, from a throwaway change
        (self.repo / "b.txt").write_text("stash me\n")
        git(self.repo, "stash", "-q")

        # the persistent dirty state under audit
        (self.repo / "a.txt").write_text("one\ntwo\n")   # unstaged modification
        (self.repo / "c.txt").write_text("staged\n")
        git(self.repo, "add", "c.txt")                    # staged addition
        (self.repo / "u.txt").write_text("untracked\n")   # untracked

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snapshot(self) -> dict:
        return {
            "status": git(self.repo, "status", "--porcelain=v1"),
            "head": git(self.repo, "rev-parse", "HEAD"),
            "stash": git(self.repo, "stash", "list"),
            "diff": git(self.repo, "diff"),
            "cached": git(self.repo, "diff", "--cached"),
            "index": git(self.repo, "ls-files", "-s"),
        }

    def test_worktree_run_does_not_touch_source_repo(self):
        before = self._snapshot()

        spec = revisions.resolve(str(self.repo))
        self.assertIs(spec.mode, revisions.InputMode.WORKTREE)

        base_a = revisions.read_blob(str(self.repo), spec.base_ref, "a.txt")
        with revisions.worktree(str(self.repo), spec.head_ref, overlay={"a.txt": base_a}) as wt:
            wt = Path(wt)
            self.assertTrue((wt / "b.txt").exists())          # untouched tracked file
            self.assertEqual((wt / "a.txt").read_text(), "one\n")   # reverted by overlay
            self.assertEqual((wt / "c.txt").read_text(), "staged\n")  # staged change present

        self.assertEqual(before, self._snapshot())

    def test_working_tree_diff_sees_staged_and_unstaged(self):
        spec = revisions.resolve(str(self.repo))
        self.assertIn("a.txt", spec.changed_paths)
        self.assertIn("c.txt", spec.changed_paths)
        self.assertIn("c.txt", spec.added)
        self.assertEqual(spec.deleted, [])

    def test_untracked_files_are_warned(self):
        spec = revisions.resolve(str(self.repo))
        self.assertIn("u.txt", spec.untracked_warnings)

    def test_commit_mode(self):
        git(self.repo, "checkout", "-q", "--", ".")   # drop unstaged
        git(self.repo, "reset", "-q")                 # unstage
        (self.repo / "a.txt").write_text("one\nthree\n")
        git(self.repo, "commit", "-qam", "change a")
        sha = git(self.repo, "rev-parse", "HEAD").strip()

        before = self._snapshot()
        spec = revisions.resolve(str(self.repo), commit=sha)
        self.assertIs(spec.mode, revisions.InputMode.COMMIT)
        self.assertEqual(spec.changed_paths, ["a.txt"])
        self.assertEqual(before, self._snapshot())


if __name__ == "__main__":
    unittest.main()
