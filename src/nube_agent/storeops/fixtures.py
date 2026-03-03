"""Fixture helpers for local evals and optional LangSmith uploads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "storeops"


def load_fixture_scenarios() -> list[dict[str, Any]]:
    directory = fixture_dir()
    scenarios = []
    for path in sorted(directory.glob("scenario_*.json")):
        scenarios.append(json.loads(path.read_text(encoding="utf-8")))
    return scenarios
