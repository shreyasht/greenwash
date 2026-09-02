"""Revision handling and worktree isolation (REQUIREMENTS_1.md §6.2, FR-7..FR-11).

Three input modes: a commit range, a single commit, the uncommitted working tree (FR-7).
Never mutate the user's working tree, index, or stash stack — use isolated git worktrees
for all runs (FR-8, NFR-5). Detect untracked files excluded from the audit and warn
(FR-9). Rename detection is disabled so renames decompose into add + delete (FR-10,
DR-3); callers disclose that in output when adds/deletes are present (FR-11).

Working-tree mode captures the dirty state with `git stash create`, which produces a
dangling commit object without touching the stash ref namespace — so NFR-5 holds.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

WORKTREE_PREFIX = "astroturf-wt-"


class InputMode(str, Enum):
    RANGE = "range"
    COMMIT = "commit"
    WORKTREE = "worktree"


class GitError(RuntimeError):
    pass


@dataclass
class DiffSpec:
    mode: InputMode
    base_ref: str
    head_ref: str
    changed_paths: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    untracked_warnings: list[str] = field(default_factory=list)

    @property
    def has_adds_or_deletes(self) -> bool:
        """FR-11: renames appear as a deletion plus an addition; disclose when either is present."""
        return bool(self.added or self.deleted)


def _git(repo_root: str, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", repo_root, *args],
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _rev_parse(repo_root: str, ref: str) -> str:
    return _git(repo_root, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def read_blob(repo_root: str, ref: str, path: str) -> bytes | None:
    """File content at `ref`, or None if the path does not exist there."""
    proc = subprocess.run(
        ["git", "-C", repo_root, "show", f"{ref}:{path}"],
        capture_output=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def _parse_range(repo_root: str, spec: str) -> tuple[str, str]:
    if "..." in spec:
        left, right = spec.split("...", 1)
        base = _git(repo_root, "merge-base", left or "HEAD", right or "HEAD").strip()
        return base, _rev_parse(repo_root, right or "HEAD")
    if ".." in spec:
        left, right = spec.split("..", 1)
        return _rev_parse(repo_root, left or "HEAD"), _rev_parse(repo_root, right or "HEAD")
    # a bare ref given to --range means "that commit's parent .. that commit"
    return _rev_parse(repo_root, f"{spec}^"), _rev_parse(repo_root, spec)


def _name_status(repo_root: str, base_ref: str, head_ref: str) -> tuple[list[str], list[str], list[str]]:
    out = _git(repo_root, "diff", "--no-renames", "--name-status", "-z", base_ref, head_ref)
    tokens = out.split("\0")
    changed: list[str] = []
    added: list[str] = []
    deleted: list[str] = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        path = tokens[i + 1]
        i += 2
        changed.append(path)
        if status[0] == "A":
            added.append(path)
        elif status[0] == "D":
            deleted.append(path)
    return sorted(changed), sorted(added), sorted(deleted)


def _untracked(repo_root: str) -> list[str]:
    out = _git(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(p for p in out.split("\0") if p)


def unified_diff(repo_root: str, base_ref: str, head_ref: str, paths: list[str]) -> dict[str, str]:
    """Zero-context unified diff per path — just the changed lines, for the static
    strictness pre-filter (§4.1) and the compile-wall fallback (§9)."""
    out: dict[str, str] = {}
    for path in paths:
        out[path] = _git(
            repo_root, "diff", "--no-color", "--no-renames", "-U0",
            base_ref, head_ref, "--", path,
        )
    return out


def resolve(repo_root: str, *, range_spec: str | None = None, commit: str | None = None) -> DiffSpec:
    """Build a DiffSpec for one of the three input modes (FR-7)."""
    if range_spec and commit:
        raise ValueError("range_spec and commit are mutually exclusive")
    repo_root = str(Path(repo_root).resolve())

    if range_spec:
        mode = InputMode.RANGE
        base_ref, head_ref = _parse_range(repo_root, range_spec)
    elif commit:
        mode = InputMode.COMMIT
        head_ref = _rev_parse(repo_root, commit)
        base_ref = _rev_parse(repo_root, f"{commit}^")
    else:
        mode = InputMode.WORKTREE
        base_ref = _rev_parse(repo_root, "HEAD")
        created = _git(repo_root, "stash", "create").strip()
        head_ref = created or base_ref

    changed, added, deleted = _name_status(repo_root, base_ref, head_ref)
    untracked = _untracked(repo_root) if mode is InputMode.WORKTREE else []
    return DiffSpec(mode, base_ref, head_ref, changed, added, deleted, untracked)


@contextmanager
def worktree(
    repo_root: str,
    ref: str,
    *,
    overlay: dict[str, bytes | None] | None = None,
    keep: bool = False,
):
    """Yield the path to an isolated checkout at `ref`.

    `overlay` maps a repo-relative path to the bytes it should hold in this checkout, or
    to None to delete it. This expresses both "apply the dirty working tree" and the
    source-only revert (test/config paths reset to base content) without hunk surgery
    (FR-10 note: revert logic stays file-level).

    Cleaned up on exit unless `keep` (FR-18). Never affects repo_root's working tree,
    index, or stash (FR-8, NFR-5).
    """
    repo_root = str(Path(repo_root).resolve())
    wt_path = tempfile.mkdtemp(prefix=WORKTREE_PREFIX)
    try:
        _git(repo_root, "worktree", "add", "--detach", "--force", wt_path, ref)
        for rel, content in (overlay or {}).items():
            target = Path(wt_path) / rel
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        yield wt_path
    finally:
        if keep:
            print(f"astroturf: kept worktree at {wt_path}")
        else:
            _git(repo_root, "worktree", "remove", "--force", wt_path, check=False)
            shutil.rmtree(wt_path, ignore_errors=True)
            _git(repo_root, "worktree", "prune", check=False)
