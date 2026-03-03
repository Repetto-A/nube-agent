"""Deterministic ranking helpers for StoreOps findings and actions."""

from __future__ import annotations

from nube_agent.storeops.models import AuditFinding, PlannedAction


def rank_findings(findings: list[AuditFinding]) -> list[AuditFinding]:
    return sorted(
        findings,
        key=lambda item: (
            -item.impact_score,
            item.risk_score,
            -item.confidence_score,
            item.issue_type,
        ),
    )


def rank_actions(actions: list[PlannedAction]) -> list[PlannedAction]:
    return sorted(
        actions,
        key=lambda item: (
            -item.impact_score,
            item.risk_score,
            -item.confidence_score,
            -len(item.target_ids),
            item.action_type,
        ),
    )
