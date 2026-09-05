"""Content-addressed response cache at data/llm_cache/<sha256>.json.

Keyed on (provider, model, prompt, schema). Makes the daily run reproducible
and lets the demo be pre-warmed before presenting. A cache hit must never
touch the network or spawn a process - callers are expected to check `get`
before doing either.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import settings


def make_key(provider_name: str, model: str, prompt: str, schema: dict[str, Any]) -> str:
    """Deterministic cache key for (provider, model, prompt, schema)."""
    payload = json.dumps(
        {"provider": provider_name, "model": model, "prompt": prompt, "schema": schema},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_for(key: str) -> Path:
    cache_dir = settings.llm_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.json"


def get(key: str) -> dict[str, Any] | None:
    """Return the cached response for `key`, or None on a miss or bad file."""
    path = _path_for(key)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def set(key: str, value: dict[str, Any]) -> None:
    """Persist `value` under `key`. Overwrites any existing entry."""
    path = _path_for(key)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(value, fh)
