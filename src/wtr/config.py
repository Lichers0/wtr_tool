"""Configuration file handling for wtr."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class WorktreeConfig:
    """Worktree-related settings."""

    default_base: str = ""  # empty = auto-detect (main or master)


@dataclass
class UIConfig:
    """UI-related settings."""

    show_status: bool = True
    show_preview: bool = True
    preview_count: int = 5


@dataclass
class PruneConfig:
    """Prune-related settings."""

    auto_suggest: bool = True


@dataclass
class Config:
    """Main configuration container."""

    worktree: WorktreeConfig = field(default_factory=WorktreeConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    prune: PruneConfig = field(default_factory=PruneConfig)


def find_config_file(repo_root: Path | None = None) -> Path | None:
    """Find config file in repo root or user config dir."""
    candidates = []

    if repo_root:
        candidates.append(repo_root / ".wtrrc")
        candidates.append(repo_root / ".wtrrc.toml")

    config_home = Path.home() / ".config" / "wtr"
    candidates.append(config_home / "config.toml")

    for path in candidates:
        if path.exists():
            return path

    return None


def load_config(repo_root: Path | None = None) -> Config:
    """Load configuration from file or return defaults."""
    config_path = find_config_file(repo_root)

    if config_path is None:
        return Config()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return Config()

    config = Config()

    if "worktree" in data:
        wt = data["worktree"]
        config.worktree = WorktreeConfig(
            default_base=wt.get("default_base", config.worktree.default_base),
        )

    if "ui" in data:
        ui = data["ui"]
        config.ui = UIConfig(
            show_status=ui.get("show_status", config.ui.show_status),
            show_preview=ui.get("show_preview", config.ui.show_preview),
            preview_count=ui.get("preview_count", config.ui.preview_count),
        )

    if "prune" in data:
        pr = data["prune"]
        config.prune = PruneConfig(
            auto_suggest=pr.get("auto_suggest", config.prune.auto_suggest),
        )

    return config
