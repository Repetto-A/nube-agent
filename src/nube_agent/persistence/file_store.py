"""Duck-typed file-backed store compatible with the store usage in this repo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from nube_agent.config import STOREOPS_DATA_DIR


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _normalize_key(key: str) -> str:
    normalized = PurePosixPath("/" + key.lstrip("/")).as_posix()
    return normalized


def _safe_relative_path(key: str) -> Path:
    parts = [part for part in PurePosixPath(_normalize_key(key)).parts if part not in {"/", ""}]
    if any(part == ".." for part in parts):
        raise ValueError(f"Invalid store key: {key}")
    return Path(*parts)


@dataclass(slots=True)
class FileStoreItem:
    namespace: tuple[str, ...]
    key: str
    value: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    score: float | None = None


class FileBackedStore:
    """Minimal store implementation for StoreBackend and StoreOps repositories.

    Methods intentionally match the exact usage in this repo:
    - get(namespace, key)
    - put(namespace, key, value)
    - search(namespace_prefix, query=None, filter=None, limit=10, offset=0)
    - aget(...)
    - aput(...)
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or STOREOPS_DATA_DIR / "store").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _namespace_root(self, namespace: tuple[str, ...]) -> Path:
        if not namespace:
            raise ValueError("Namespace must not be empty")
        base = self.root
        for segment in namespace:
            if not segment or segment in {".", ".."}:
                raise ValueError(f"Invalid namespace segment: {segment!r}")
            base /= segment
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _item_path(self, namespace: tuple[str, ...], key: str) -> Path:
        ns_root = self._namespace_root(namespace)
        relative = _safe_relative_path(key)
        return ns_root / relative.parent / f"{relative.name}.store.json"

    def _write_item(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
        *,
        created_at: str,
        updated_at: str,
    ) -> None:
        target = self._item_path(namespace, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "namespace": list(namespace),
            "key": _normalize_key(key),
            "value": value,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_item_file(self, path: Path) -> FileStoreItem:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return FileStoreItem(
            namespace=tuple(raw["namespace"]),
            key=raw["key"],
            value=raw["value"],
            created_at=datetime.fromisoformat(raw["created_at"]),
            updated_at=datetime.fromisoformat(raw["updated_at"]),
        )

    def get(self, namespace: tuple[str, ...], key: str) -> FileStoreItem | None:
        target = self._item_path(namespace, key)
        if not target.exists():
            return None
        return self._read_item_file(target)

    def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any] | None,
        index: list[str] | bool | None = None,
        *,
        ttl: float | None = None,
    ) -> None:
        del index, ttl
        target = self._item_path(namespace, key)
        if value is None:
            if target.exists():
                target.unlink()
            return

        existing = self.get(namespace, key)
        now = _utc_now_iso()
        created_at = (
            existing.created_at.isoformat() if existing is not None else now
        )
        self._write_item(
            namespace,
            key,
            value,
            created_at=created_at,
            updated_at=now,
        )

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        /,
        *,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[FileStoreItem]:
        del query
        prefix_root = self._namespace_root(namespace_prefix)
        if not prefix_root.exists():
            return []

        items: list[FileStoreItem] = []
        for path in prefix_root.rglob("*.store.json"):
            item = self._read_item_file(path)
            if filter and not all(item.value.get(k) == v for k, v in filter.items()):
                continue
            items.append(item)

        items.sort(key=lambda item: item.key)
        return items[offset : offset + limit]

    async def aget(self, namespace: tuple[str, ...], key: str) -> FileStoreItem | None:
        return self.get(namespace, key)

    async def aput(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any] | None,
        index: list[str] | bool | None = None,
        *,
        ttl: float | None = None,
    ) -> None:
        self.put(namespace, key, value, index=index, ttl=ttl)
