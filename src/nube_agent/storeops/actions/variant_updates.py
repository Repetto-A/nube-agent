from __future__ import annotations

from nube_agent.api import mutation_firewall, request
from nube_agent.storeops.models import PlannedAction, StructuredDiff


def preview_bulk_variant_update(action: PlannedAction) -> list[StructuredDiff]:
    diffs: list[StructuredDiff] = []
    product_id = action.params["product_id"]
    for item in action.params.get("updates", []):
        before = {
            "price": item.get("current_price"),
            "stock": item.get("current_stock"),
        }
        after = {
            key: value
            for key, value in {"price": item.get("price"), "stock": item.get("stock")}.items()
            if value is not None
        }
        diffs.append(
            StructuredDiff(
                action_id=action.action_id,
                target_type="variant",
                target_id=str(item["variant_id"]),
                before=before,
                after=after,
                summary=f"Update variant {item['variant_id']} on product {product_id}.",
            )
        )
    return diffs


def apply_bulk_variant_update(action: PlannedAction, *, dry_run: bool) -> list[StructuredDiff]:
    updates = action.params.get("updates", [])
    for item in updates:
        if "variant_id" not in item:
            raise ValueError("bulk variant updates require variant_id")
        if item.get("price") is None and item.get("stock") is None:
            raise ValueError("each variant update needs price or stock")

    diffs = preview_bulk_variant_update(action)
    product_id = action.params["product_id"]
    with mutation_firewall(dry_run):
        if dry_run:
            return diffs
        for item in updates:
            body = {
                key: value
                for key, value in {"price": item.get("price"), "stock": item.get("stock")}.items()
                if value is not None
            }
            request(
                "PUT",
                f"/products/{product_id}/variants/{item['variant_id']}",
                json_body=body,
            )
    return diffs
