"""NFR-5 property test: a greenwash run leaves the repo's working tree, index, and stash
list byte-identical. This is the first thing BUILD_PLAN.md §3 step 1 must make pass, and
it must stay green for the life of the project.
"""

import unittest


class NonDestructiveTest(unittest.TestCase):
    @unittest.skip("BUILD_PLAN.md §3 step 1 — revisions.worktree not implemented")
    def test_worktree_run_does_not_touch_source_repo(self):
        # Arrange: a scratch git repo with a known dirty state.
        # Act: run greenwash against it (working-tree mode).
        # Assert: `git status --porcelain`, `git rev-parse HEAD`, index hash, and
        #         `git stash list` are identical before and after.
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
