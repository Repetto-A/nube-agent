"""Repositories for the virtual filesystem persisted in the file-backed store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from nube_agent.persistence.file_store import FileBackedStore

FILESYSTEM_NAMESPACE = ("filesystem",)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _make_file_value(content: str, *, created_at: str | None = None) -> dict[str, Any]:
    lines = content.splitlines()
    return {
        "content": lines,
        "created_at": created_at or _utc_now_iso(),
        "modified_at": _utc_now_iso(),
    }


@lru_cache(maxsize=1)
def get_store() -> FileBackedStore:
    return FileBackedStore()


class VirtualFilesystem:
    def __init__(
        self,
        store: FileBackedStore | None = None,
        namespace: tuple[str, ...] = FILESYSTEM_NAMESPACE,
    ) -> None:
        self.store = store or get_store()
        self.namespace = namespace

    def exists(self, path: str) -> bool:
        return self.store.get(self.namespace, path) is not None

    def read_text(self, path: str, default: str | None = None) -> str | None:
        item = self.store.get(self.namespace, path)
        if item is None:
            return default
        return "\n".join(item.value.get("content", []))

    def write_text(self, path: str, content: str) -> None:
        existing = self.store.get(self.namespace, path)
        created_at = None
        if existing is not None:
            created_at = existing.value.get("created_at")
        self.store.put(
            self.namespace,
            path,
            _make_file_value(content, created_at=created_at),
        )

    def read_json(self, path: str, default: Any = None) -> Any:
        raw = self.read_text(path)
        if raw is None or raw == "":
            return default
        return json.loads(raw)

    def write_json(self, path: str, payload: Any) -> None:
        self.write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))

    def list_paths(self, prefix: str) -> list[str]:
        items = self.store.search(self.namespace, limit=10_000, offset=0)
        return sorted(item.key for item in items if item.key.startswith(prefix))


@lru_cache(maxsize=1)
def get_virtual_filesystem() -> VirtualFilesystem:
    return VirtualFilesystem()
