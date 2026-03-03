from __future__ import annotations

from datetime import UTC, datetime

from nube_agent.api import mutation_firewall, request, store_locale
from nube_agent.storeops.models import PlannedAction, StructuredDiff


def _page_body(title: str, theme: str) -> dict:
    locale = store_locale()
    today = datetime.now(UTC).date().isoformat()
    content = (
        f"<h2>{title}</h2><p>Updated on {today}.</p>"
        f"<p>This page now addresses {theme} with clearer next-step guidance.</p>"
    )
    return {
        "page": {
            "publish": True,
            "i18n": {
                locale: {
                    "title": title,
                    "content": content,
                }
            },
        }
    }


def preview_page_template_update(action: PlannedAction) -> list[StructuredDiff]:
    params = action.params
    after = _page_body(params["title"], params.get("theme", "operations"))
    return [
        StructuredDiff(
            action_id=action.action_id,
            target_type="page",
            target_id=str(params["page_id"]),
            before=params.get("before", {}),
            after=after,
            summary=f"Refresh page {params['page_id']} using a StoreOps template.",
        )
    ]


def apply_page_template_update(action: PlannedAction, *, dry_run: bool) -> list[StructuredDiff]:
    diffs = preview_page_template_update(action)
    params = action.params
    with mutation_firewall(dry_run):
        if dry_run:
            return diffs
        request("PUT", f"/pages/{params['page_id']}", json_body=diffs[0].after)
    return diffs
