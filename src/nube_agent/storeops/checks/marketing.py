from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def run_marketing_checks(
    snapshot: dict[str, Any],
    thresholds: StoreOpsThresholds,
) -> list[AuditFinding]:
    coupons = snapshot.get("coupons", [])
    checkouts = snapshot.get("checkouts", [])
    findings: list[AuditFinding] = []
    now = datetime.now(UTC)

    misconfigured = []
    for coupon in coupons:
        reasons: list[str] = []
        coupon_type = coupon.get("type")
        value = coupon.get("value")
        if coupon_type in {"percentage", "absolute"} and str(value or "") in {"", "0", "0.0"}:
            reasons.append("missing_value")
        end_date = _parse_datetime(coupon.get("end_date"))
        if end_date is not None and end_date < now:
            reasons.append("expired")
        if (
            not coupon.get("products")
            and not coupon.get("categories")
            and not coupon.get("end_date")
        ):
            reasons.append("too_broad")
        if not coupon.get("max_uses"):
            reasons.append("missing_max_uses")
        if reasons:
            misconfigured.append((coupon, reasons))

    if misconfigured:
        findings.append(
            AuditFinding(
                issue_id="marketing-coupon-issues",
                issue_type="marketing.coupon_configuration",
                title="Coupons need guardrails",
                summary=(
                    f"{len(misconfigured)} coupons are expired, too broad, "
                    "or missing constraints."
                ),
                severity="high",
                impact_score=4,
                risk_score=3,
                confidence_score=5,
                evidence=[
                    AuditEvidence(
                        source="coupons",
                        resource_type="coupon",
                        resource_id=str(coupon.get("id")),
                        message=f"Coupon {coupon.get('code')} flagged for: {', '.join(reasons)}.",
                    )
                    for coupon, reasons in misconfigured[:10]
                ],
                resource_ids=[str(coupon.get("id")) for coupon, _ in misconfigured],
            )
        )

    lookback = timedelta(days=thresholds.abandoned_checkout_lookback_days)
    current_period_start = now - lookback
    previous_period_start = now - lookback * 2
    current_count = 0
    previous_count = 0
    for checkout in checkouts:
        created_at = _parse_datetime(checkout.get("created_at"))
        if created_at is None:
            continue
        if current_period_start <= created_at <= now:
            current_count += 1
        elif previous_period_start <= created_at < current_period_start:
            previous_count += 1

    if current_count >= 3 and (previous_count == 0 or current_count > previous_count):
        findings.append(
            AuditFinding(
                issue_id="marketing-abandoned-trend",
                issue_type="marketing.abandoned_checkout_trend",
                title="Abandoned checkouts are elevated",
                summary=(
                    f"{current_count} abandoned checkouts were created in the last "
                    f"{thresholds.abandoned_checkout_lookback_days} days."
                ),
                severity="medium",
                impact_score=4,
                risk_score=2,
                confidence_score=4,
                evidence=[
                    AuditEvidence(
                        source="checkouts",
                        resource_type="checkout",
                        resource_id=str(checkout.get("id")),
                        message="Recent abandoned checkout contributes to the upward trend.",
                    )
                    for checkout in checkouts[:10]
                ],
                resource_ids=[str(checkout.get("id")) for checkout in checkouts[:10]],
            )
        )

    return findings
