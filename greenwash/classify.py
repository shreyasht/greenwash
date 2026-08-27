"""Change classification (REQUIREMENTS_1.md §6.1, FR-1..FR-6).

Classify every changed path as source | test | config | neutral, attributed to its
owning build module. Test detection comes from build-tool convention (src/test/,
src/integrationTest/, src/testFixtures/) before filename guessing (FR-2). Config is
anything that can alter what the build enforces (FR-3). Overridable per repo (FR-4) and
reported in output so a user can dispute it (FR-5). Module identity is the repo-relative
directory of the build file that owns the path (FR-6).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from greenwash.revisions import WORKTREE_PREFIX


class Kind(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    NEUTRAL = "neutral"


@dataclass
class ClassifiedPath:
    path: str
    kind: Kind
    module: str  # repo-relative dir of the build file that owns the path (FR-6); "." = root
    reason: str  # human-readable basis for the classification (FR-5)


# Build-tool test source roots (FR-2). A path under one of these is test regardless of
# extension — test resources are fixture data, not enforcement config.
TEST_ROOTS = (
    "src/test/",
    "src/integrationTest/",
    "src/intTest/",
    "src/integration-test/",
    "src/testFixtures/",
    "src/functionalTest/",
    "src/it/",
)

# Filename fallback for non-standard layouts (FR-2).
TEST_NAME_GLOBS = (
    "*Test.java", "*Tests.java", "*TestCase.java", "*IT.java", "*ITCase.java",
    "*Test.kt", "*Tests.kt", "*Spec.groovy", "*Spec.scala",
)

SOURCE_ROOTS = ("src/main/",)
SOURCE_EXTS = (".java", ".kt", ".scala", ".groovy")

# Things that can alter what the build enforces (FR-3).
CONFIG_EXACT = {
    "pom.xml",
    "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts",
    "gradle.properties",
}
CONFIG_PATH_SUBSTRINGS = (
    ".github/workflows/",
    ".circleci/",
    ".mvn/",
    "gradle/",  # wrapper properties, version catalogs
    "config/checkstyle/", "config/spotbugs/", "config/pmd/",
)
CONFIG_NAME_GLOBS = (
    "*checkstyle*.xml", "*spotbugs*.xml", "*findbugs*.xml", "*pmd*.xml",
    "*suppression*.xml",
    "libs.versions.toml",
    ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml",
)

_WALK_SKIP = {".git", "target", "build", "node_modules", ".gradle", ".idea", "out"}
_BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")


def _under(path: str, root: str) -> bool:
    return path.startswith(root) or ("/" + root) in path


def _discover_modules(repo_root: str) -> set[str]:
    """Repo-relative dirs that contain a build file. '' represents the root."""
    dirs: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _WALK_SKIP and not d.startswith(WORKTREE_PREFIX)
        ]
        if any(f in filenames for f in _BUILD_FILES):
            rel = os.path.relpath(dirpath, repo_root).replace(os.sep, "/")
            dirs.add("" if rel == "." else rel)
    return dirs or {""}


def _module_of(path: str, module_dirs: set[str]) -> str:
    parts = PurePosixPath(path).parts
    for i in range(len(parts) - 1, -1, -1):
        cand = "/".join(parts[:i])
        if cand in module_dirs:
            return cand or "."
    return "."


def _classify_one(path: str, overrides: dict[str, str]) -> tuple[Kind, str]:
    name = path.rsplit("/", 1)[-1]

    for pattern, kind in overrides.items():
        if fnmatch(path, pattern):
            return Kind(kind), f"override: matches {pattern!r} (FR-4)"

    for root in TEST_ROOTS:
        if _under(path, root):
            return Kind.TEST, f"under test source root {root!r} (FR-2)"

    if name in CONFIG_EXACT:
        return Kind.CONFIG, f"build file {name!r} (FR-3)"
    for sub in CONFIG_PATH_SUBSTRINGS:
        if sub in path:
            return Kind.CONFIG, f"path contains {sub!r} (FR-3)"
    for glob in CONFIG_NAME_GLOBS:
        if fnmatch(name, glob):
            return Kind.CONFIG, f"filename matches {glob!r} (FR-3)"

    for glob in TEST_NAME_GLOBS:
        if fnmatch(name, glob):
            return Kind.TEST, f"filename matches {glob!r} (FR-2 fallback)"

    for root in SOURCE_ROOTS:
        if _under(path, root):
            return Kind.SOURCE, f"under main source root {root!r}"
    if name.endswith(SOURCE_EXTS):
        return Kind.SOURCE, "JVM source file outside a recognized root"

    return Kind.NEUTRAL, "no source, test, or config signal"


def classify(
    paths: list[str],
    repo_root: str,
    overrides: dict[str, str] | None = None,
) -> list[ClassifiedPath]:
    repo_root = str(Path(repo_root).resolve())
    module_dirs = _discover_modules(repo_root)
    overrides = overrides or {}
    out: list[ClassifiedPath] = []
    for path in paths:
        kind, reason = _classify_one(path, overrides)
        out.append(ClassifiedPath(path, kind, _module_of(path, module_dirs), reason))
    return out
