from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from backend.config import CACHE_DIR, CACHE_TTL_SECONDS


class JsonCache:
    def __init__(self, directory: Path = CACHE_DIR, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.directory = directory
        self.ttl_seconds = ttl_seconds
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path_for(key)
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        created_at = float(payload.get("created_at", 0))
        if self.ttl_seconds > 0 and time.time() - created_at > self.ttl_seconds:
            return None

        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def set(self, key: str, data: dict[str, Any]) -> None:
        path = self._path_for(key)
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                {"created_at": time.time(), "data": data},
                file,
                ensure_ascii=False,
                indent=2,
            )
