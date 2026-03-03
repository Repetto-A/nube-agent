from __future__ import annotations

from nube_agent.api import mutation_firewall, request
from nube_agent.storeops.models import PlannedAction, StructuredDiff


def preview_coupon_change(action: PlannedAction) -> list[StructuredDiff]:
    params = action.params
    before = params.get("before", {})
    after = params.get("after", {})
    target_id = str(params.get("coupon_id", "new"))
    return [
        StructuredDiff(
            action_id=action.action_id,
            target_type="coupon",
            target_id=target_id,
            before=before,
            after=after,
            summary="Tighten coupon guardrails and validity.",
        )
    ]


def apply_coupon_change(action: PlannedAction, *, dry_run: bool) -> list[StructuredDiff]:
    diffs = preview_coupon_change(action)
    params = action.params
    with mutation_firewall(dry_run):
        if dry_run:
            return diffs
        coupon_id = params.get("coupon_id")
        if coupon_id:
            request("PUT", f"/coupons/{coupon_id}", json_body=params["after"])
        else:
            request("POST", "/coupons", json_body=params["after"])
    return diffs
