"""Config file loading (REQUIREMENTS_1.md §6.6 FR-30; format per DR-6).

`.greenwash.toml` at repo root, parsed with stdlib `tomllib`. Keys: build command,
report globs, classification overrides, confirmation count, module scoping, per-verdict
exit behaviour. All keys optional; every value has a default so greenwash runs with no
config file at all.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field

CONFIG_FILENAME = ".greenwash.toml"


@dataclass
class Config:
    build_command: list[str] | None = None
    report_globs: list[str] = field(default_factory=list)
    classification_overrides: dict[str, str] = field(default_factory=dict)
    confirm_count: int = 2
    confirm_mode: str = "isolated"
    module_scope: bool = True
    timeout_s: int = 1800
    exit_overrides: dict[str, int] = field(default_factory=dict)


def load(repo_root: str) -> Config:
    raise NotImplementedError  # BUILD_PLAN.md §3 step 7
