from __future__ import annotations

from typing import Any

from nube_agent.api import mutation_firewall, request, store_language
from nube_agent.storeops.models import PlannedAction, StructuredDiff


def _build_suggested_copy(product_id: str, current_name: str) -> dict[str, Any]:
    improved_title = current_name.strip() or f"Product {product_id}"
    if " | " not in improved_title:
        improved_title = f"{improved_title} | Tiendanube"
    improved_description = (
        f"<p>{current_name or f'Product {product_id}'} optimized for storefront clarity, "
        "benefits, and key buying details.</p>"
    )
    return {
        "name": {store_language(): improved_title},
        "description": {store_language(): improved_description},
    }


def preview_product_copy_update(action: PlannedAction) -> list[StructuredDiff]:
    diffs: list[StructuredDiff] = []
    for product in action.params.get("products", []):
        before = {
            "name": product.get("current_name"),
            "description": product.get("current_description"),
        }
        after = _build_suggested_copy(
            str(product["product_id"]),
            product.get("current_name", "Product"),
        )
        diffs.append(
            StructuredDiff(
                action_id=action.action_id,
                target_type="product",
                target_id=str(product["product_id"]),
                before=before,
                after=after,
                summary=f"Refresh copy for product {product['product_id']}.",
            )
        )
    return diffs


def apply_product_copy_update(action: PlannedAction, *, dry_run: bool) -> list[StructuredDiff]:
    diffs = preview_product_copy_update(action)
    with mutation_firewall(dry_run):
        if dry_run:
            return diffs
        for diff in diffs:
            request("PUT", f"/products/{diff.target_id}", json_body=diff.after)
    return diffs
