"""Change classification (REQUIREMENTS_1.md §6.1, FR-1..FR-6).

Classify every changed path as source | test | config | neutral, attributed to its
owning build module. Test detection comes from build-tool convention (src/test/,
src/integrationTest/, src/testFixtures/) before filename guessing (FR-2). Config is
anything that can alter what the build enforces (FR-3). Overridable per repo (FR-4) and
reported in output so a user can dispute it (FR-5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Kind(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    NEUTRAL = "neutral"


@dataclass
class ClassifiedPath:
    path: str
    kind: Kind
    module: str  # repo-relative dir of the build file that owns the path (FR-6)
    reason: str  # human-readable basis for the classification (FR-5)


def classify(paths: list[str], repo_root: str, overrides: dict | None = None) -> list[ClassifiedPath]:
    raise NotImplementedError  # BUILD_PLAN.md §3 step 2
