from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_project_context() -> dict[str, Any]:
    return _read_yaml(ROOT / "project-context.yml")


def load_tracked_items() -> dict[str, Any]:
    return _read_yaml(ROOT / "tracked-items.yml")

