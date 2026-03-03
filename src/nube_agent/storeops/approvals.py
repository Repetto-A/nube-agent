"""Approval and confirmation-code helpers."""

from __future__ import annotations

from nube_agent.storeops.models import ApprovalChallenge, PlannedAction


def build_confirmation_code(action_type: str, ordinal: int) -> str:
    prefix = {
        "bulk_variant_update": "PRICE",
        "coupon_update": "COUPON",
        "page_update": "PAGE",
        "product_copy_update": "COPY",
        "memory_note": "NOTE",
    }.get(action_type, "APPLY")
    return f"{prefix}-{ordinal:02d}"


def needs_confirmation(action: PlannedAction) -> bool:
    return action.high_risk and bool(action.confirmation_code)


def build_approval_challenge(action: PlannedAction) -> ApprovalChallenge | None:
    if not needs_confirmation(action):
        return None
    return ApprovalChallenge(
        action_id=action.action_id,
        code=action.confirmation_code or "",
        reason=action.confirmation_reason or "High-risk action requires a typed confirmation code.",
    )


def validate_confirmation(action: PlannedAction, provided_code: str | None) -> bool:
    if not needs_confirmation(action):
        return True
    return (provided_code or "").strip().upper() == (action.confirmation_code or "").upper()
