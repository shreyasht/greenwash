"""Config file loading (REQUIREMENTS_1.md §6.6 FR-30; format per DR-6).

`.greenwash.toml` at repo root, parsed with stdlib `tomllib`. Keys: build command,
report globs, classification overrides, confirmation count, module scoping, per-verdict
exit behaviour. All keys optional; every value has a default so greenwash runs with no
config file at all.
"""

from __future__ import annotations

import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

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


def _as_command(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return shlex.split(value)
    return [str(part) for part in value]


def load(repo_root: str) -> Config:
    """Load .greenwash.toml from the repo root. Every key is optional; a missing file
    yields an all-defaults Config so greenwash runs with no config at all."""
    path = Path(repo_root) / CONFIG_FILENAME
    if not path.is_file():
        return Config()
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    defaults = Config()
    return Config(
        build_command=_as_command(data.get("build_command")),
        report_globs=list(data.get("report_globs", [])),
        classification_overrides=dict(data.get("classification_overrides", {})),
        confirm_count=int(data.get("confirm_count", defaults.confirm_count)),
        confirm_mode=str(data.get("confirm_mode", defaults.confirm_mode)),
        module_scope=bool(data.get("module_scope", defaults.module_scope)),
        timeout_s=int(data.get("timeout_s", defaults.timeout_s)),
        exit_overrides={str(k): int(v) for k, v in data.get("exit_overrides", {}).items()},
    )
