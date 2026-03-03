from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from nube_agent.storeops.config import StoreOpsThresholds
from nube_agent.storeops.models import AuditEvidence, AuditFinding


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_order_checks(
    snapshot: dict[str, Any],
    thresholds: StoreOpsThresholds,
) -> list[AuditFinding]:
    del thresholds
    orders = snapshot.get("orders", [])
    findings: list[AuditFinding] = []
    now = datetime.now(UTC)
    stuck_orders = []
    pending_orders = []

    for order in orders:
        created_at = _parse_datetime(order.get("created_at"))
        age_hours = None
        if created_at is not None:
            age_hours = (now - created_at).total_seconds() / 3600

        status = str(order.get("status", ""))
        payment_status = str(order.get("payment_status", ""))
        shipping_status = str(order.get("shipping_status", ""))
        if age_hours is not None and age_hours >= 72 and status == "open":
            stuck_orders.append((order, age_hours))

        if payment_status not in {"paid", "authorized"} or shipping_status != "fulfilled":
            pending_orders.append(order)

    if stuck_orders:
        findings.append(
            AuditFinding(
                issue_id="orders-stuck-status",
                issue_type="orders.stuck_status",
                title="Orders stuck in open status",
                summary=f"{len(stuck_orders)} orders have remained open longer than 72 hours.",
                severity="high",
                impact_score=4,
                risk_score=3,
                confidence_score=4,
                evidence=[
                    AuditEvidence(
                        source="orders",
                        resource_type="order",
                        resource_id=str(order.get("id")),
                        message=(
                            f"Order {order.get('number')} has been open for "
                            f"{age_hours:.1f} hours."
                        ),
                    )
                    for order, age_hours in stuck_orders[:10]
                ],
                resource_ids=[str(order.get("id")) for order, _ in stuck_orders],
            )
        )

    if pending_orders:
        findings.append(
            AuditFinding(
                issue_id="orders-unpaid-unfulfilled",
                issue_type="orders.pending_follow_up",
                title="Orders need payment or fulfillment follow-up",
                summary=f"{len(pending_orders)} orders are unpaid or unfulfilled.",
                severity="medium",
                impact_score=4,
                risk_score=2,
                confidence_score=5,
                evidence=[
                    AuditEvidence(
                        source="orders",
                        resource_type="order",
                        resource_id=str(order.get("id")),
                        message=(
                            f"Order {order.get('number')} payment={order.get('payment_status')} "
                            f"shipping={order.get('shipping_status')}."
                        ),
                    )
                    for order in pending_orders[:10]
                ],
                resource_ids=[str(order.get("id")) for order in pending_orders],
            )
        )

    return findings
