"""Revision handling and worktree isolation (REQUIREMENTS_1.md §6.2, FR-7..FR-11).

Three input modes: a commit range, a single commit, the uncommitted working tree (FR-7).
Never mutate the user's working tree, index, or stash stack — use isolated git worktrees
for all runs (FR-8, NFR-5). Detect untracked source files and warn (FR-9). Rename
detection is disabled so renames decompose into add + delete (FR-10, DR-3); that
consequence is disclosed in output (FR-11).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum


class InputMode(str, Enum):
    RANGE = "range"
    COMMIT = "commit"
    WORKTREE = "worktree"


@dataclass
class DiffSpec:
    mode: InputMode
    base_ref: str
    head_ref: str  # for WORKTREE mode, the dirty tree; represented by a synthetic ref/stash
    changed_paths: list[str]
    added: list[str]
    deleted: list[str]
    untracked_warnings: list[str]


def resolve(repo_root: str, mode: InputMode, *, base: str | None, commit: str | None) -> DiffSpec:
    raise NotImplementedError  # BUILD_PLAN.md §3 step 1


@contextmanager
def worktree(repo_root: str, ref: str, *, apply_paths: dict[str, str] | None = None):
    """Yield a path to an isolated checkout at `ref`, optionally with specific paths
    overwritten to their base content (the source-only revert). Cleaned up on exit
    unless the caller opts into --keep. Must never affect repo_root's tree/index/stash.
    """
    raise NotImplementedError  # BUILD_PLAN.md §3 step 1
