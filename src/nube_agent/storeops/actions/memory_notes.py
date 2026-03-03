from __future__ import annotations

from nube_agent.persistence.repositories import get_virtual_filesystem
from nube_agent.storeops.models import PlannedAction, StructuredDiff


def preview_memory_note(action: PlannedAction) -> list[StructuredDiff]:
    path = action.params.get("path", "/memories/storeops/preferences.json")
    fs = get_virtual_filesystem()
    before = {}
    existing = fs.read_json(path, default=None)
    if existing is not None:
        before = existing
    after = action.params.get("note", {})
    return [
        StructuredDiff(
            action_id=action.action_id,
            target_type="memory",
            target_id=path,
            before=before,
            after=after,
            summary="Persist a recurring StoreOps note.",
        )
    ]


def apply_memory_note(action: PlannedAction, *, dry_run: bool) -> list[StructuredDiff]:
    diffs = preview_memory_note(action)
    if dry_run:
        return diffs
    fs = get_virtual_filesystem()
    fs.write_json(action.params["path"], action.params["note"])
    return diffs
