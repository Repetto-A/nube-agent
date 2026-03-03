from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from nube_agent.config import (
    STOREOPS_CONFIRMATION_REQUIRED_PRICE_DELTA_PCT,
    STOREOPS_CONFIRMATION_REQUIRED_VARIANT_COUNT,
)
from nube_agent.storeops.approvals import build_confirmation_code
from nube_agent.storeops.models import ActionPlan, AuditFinding, PlannedAction
from nube_agent.storeops.scoring import rank_actions


def _find_resources(finding: AuditFinding) -> list[str]:
    return finding.resource_ids[:]


def build_action_plan(
    findings: list[AuditFinding],
    snapshot: dict[str, Any],
    *,
    report_path: str,
    dry_run: bool,
) -> ActionPlan:
    actions: list[PlannedAction] = []
    ordinal = 1
    products_by_id = {str(product.get("id")): product for product in snapshot.get("products", [])}
    variants_by_id = {}
    for product in snapshot.get("products", []):
        for variant in product.get("variants", []):
            variants_by_id[str(variant.get("id"))] = (product, variant)
    coupons_by_id = {str(coupon.get("id")): coupon for coupon in snapshot.get("coupons", [])}
    pages = snapshot.get("pages", [])

    for finding in findings:
        if finding.issue_type == "catalog.weak_content":
            targets = []
            for product_id in _find_resources(finding)[:5]:
                product = products_by_id.get(product_id)
                if product is None:
                    continue
                current_name = (
                    next(iter(product.get("name", {}).values()), "")
                    if isinstance(product.get("name"), dict)
                    else product.get("name", "")
                )
                current_description = (
                    next(iter(product.get("description", {}).values()), "")
                    if isinstance(product.get("description"), dict)
                    else product.get("description", "")
                )
                targets.append(
                    {
                        "product_id": product_id,
                        "current_name": current_name,
                        "current_description": current_description,
                    }
                )
            if targets:
                action_id = f"action-{ordinal}"
                actions.append(
                    PlannedAction(
                        action_id=action_id,
                        action_type="product_copy_update",
                        title="Improve product titles and descriptions",
                        summary="Generate stronger storefront copy for weak catalog entries.",
                        impact_score=4,
                        risk_score=2,
                        confidence_score=4,
                        target_ids=[str(item["product_id"]) for item in targets],
                        params={"products": targets},
                    )
                )
                finding.recommended_action_ids.append(action_id)
                ordinal += 1

        if finding.issue_type in {"catalog.variant_pricing", "catalog.low_stock_best_seller"}:
            updates = []
            if finding.issue_type == "catalog.variant_pricing":
                resource_ids = _find_resources(finding)
                for variant_id in resource_ids[:5]:
                    product, variant = variants_by_id.get(variant_id, ({}, {}))
                    if not variant:
                        continue
                    current_price = variant.get("price")
                    current_stock = variant.get("stock")
                    next_price = (
                        "49.99" if str(current_price or "") in {"0", "0.0", ""} else current_price
                    )
                    updates.append(
                        {
                            "variant_id": int(variant_id),
                            "current_price": current_price,
                            "current_stock": current_stock,
                            "price": next_price,
                            "stock": current_stock,
                            "product_id": product.get("id"),
                        }
                    )
            else:
                for product_id in _find_resources(finding)[:5]:
                    product = products_by_id.get(product_id)
                    if product is None:
                        continue
                    for variant in product.get("variants", [])[:3]:
                        variant_id = variant.get("id")
                        if variant_id is None:
                            continue
                        current_stock = variant.get("stock")
                        updates.append(
                            {
                                "variant_id": int(variant_id),
                                "current_price": variant.get("price"),
                                "current_stock": current_stock,
                                "price": variant.get("price"),
                                "stock": max(int(current_stock or 0), 10),
                                "product_id": product.get("id"),
                            }
                        )

            if updates:
                high_risk = len(updates) >= STOREOPS_CONFIRMATION_REQUIRED_VARIANT_COUNT
                if not high_risk:
                    for item in updates:
                        try:
                            before = float(item.get("current_price") or 0)
                            after = float(item.get("price") or before)
                        except (TypeError, ValueError):
                            continue
                        if (
                            before > 0
                            and abs(after - before) / before * 100
                            >= STOREOPS_CONFIRMATION_REQUIRED_PRICE_DELTA_PCT
                        ):
                            high_risk = True
                            break

                product_id = updates[0]["product_id"]
                if product_id is not None:
                    action_id = f"action-{ordinal}"
                    actions.append(
                        PlannedAction(
                            action_id=action_id,
                            action_type="bulk_variant_update",
                            title="Normalize variant pricing or stock",
                            summary="Preview and apply variant-level catalog fixes.",
                            impact_score=5,
                            risk_score=4 if high_risk else 3,
                            confidence_score=4,
                            target_ids=[str(item["variant_id"]) for item in updates],
                            params={"product_id": product_id, "updates": updates},
                            high_risk=high_risk,
                            confirmation_code=build_confirmation_code(
                                "bulk_variant_update", ordinal
                            )
                            if high_risk
                            else None,
                            confirmation_reason=(
                                "Bulk variant updates can change live pricing "
                                "or stock."
                            ),
                        )
                    )
                    finding.recommended_action_ids.append(action_id)
                    ordinal += 1

        if finding.issue_type == "marketing.coupon_configuration":
            coupon_id = _find_resources(finding)[0] if _find_resources(finding) else None
            coupon = coupons_by_id.get(str(coupon_id)) if coupon_id else None
            if coupon:
                high_risk = (
                    not coupon.get("end_date")
                    and not coupon.get("products")
                    and not coupon.get("categories")
                )
                after = dict(coupon)
                after["end_date"] = (
                    after.get("end_date") or (datetime.now(UTC) + timedelta(days=7)).isoformat()
                )
                after["max_uses"] = after.get("max_uses") or 100
                action_id = f"action-{ordinal}"
                actions.append(
                    PlannedAction(
                        action_id=action_id,
                        action_type="coupon_update",
                        title="Tighten coupon constraints",
                        summary="Add expiry or max-use guardrails to risky coupons.",
                        impact_score=4,
                        risk_score=4 if high_risk else 2,
                        confidence_score=4,
                        target_ids=[str(coupon_id)],
                        params={"coupon_id": int(coupon_id), "before": coupon, "after": after},
                        high_risk=high_risk,
                        confirmation_code=build_confirmation_code("coupon_update", ordinal)
                        if high_risk
                        else None,
                        confirmation_reason="This coupon change affects a broad promotion.",
                    )
                )
                finding.recommended_action_ids.append(action_id)
                ordinal += 1

        if (
            finding.issue_type in {"marketing.abandoned_checkout_trend", "orders.pending_follow_up"}
            and pages
        ):
            page = pages[0]
            action_id = f"action-{ordinal}"
            actions.append(
                PlannedAction(
                    action_id=action_id,
                    action_type="page_update",
                    title="Refresh a help page from template",
                    summary=(
                        "Update FAQ or shipping guidance to reduce repetitive "
                        "support friction."
                    ),
                    impact_score=3,
                    risk_score=2,
                    confidence_score=3,
                    target_ids=[str(page.get("id"))],
                    params={
                        "page_id": int(page.get("id")),
                        "title": "Shipping and order help",
                        "theme": "shipping times, payments, and checkout recovery",
                        "before": page,
                    },
                )
            )
            finding.recommended_action_ids.append(action_id)
            ordinal += 1

    note_payload = {
        "issue_types": [finding.issue_type for finding in findings],
        "summary": f"Last audit found {len(findings)} issues worth follow-up.",
    }
    actions.append(
        PlannedAction(
            action_id=f"action-{ordinal}",
            action_type="memory_note",
            title="Persist a recurring StoreOps note",
            summary="Save a compact audit summary to long-term memory.",
            impact_score=2,
            risk_score=1,
            confidence_score=5,
            target_ids=["/memories/storeops/preferences.json"],
            params={
                "path": "/memories/storeops/preferences.json",
                "note": note_payload,
            },
            approval_required=True,
        )
    )

    actions = rank_actions(actions)
    summary = f"Found {len(findings)} issues and prepared {len(actions)} recommended actions."
    return ActionPlan(
        plan_id=f"plan-{uuid4().hex[:8]}",
        audit_id=f"audit-{uuid4().hex[:8]}",
        summary=summary,
        dry_run=dry_run,
        report_path=report_path,
        findings=findings,
        actions=actions,
    )
