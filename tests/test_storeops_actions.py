from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nube_agent.persistence.file_store import FileBackedStore
from nube_agent.persistence.repositories import VirtualFilesystem
from nube_agent.storeops.actions.variant_updates import apply_bulk_variant_update
from nube_agent.storeops.audit_runner import apply_saved_plan
from nube_agent.storeops.memory import save_plan
from nube_agent.storeops.models import ActionPlan, PlannedAction


def test_dry_run_returns_diffs_and_does_not_call_mutation_endpoints():
    action = PlannedAction(
        action_id="action-1",
        action_type="bulk_variant_update",
        title="Bulk variant update",
        summary="Preview catalog changes.",
        impact_score=5,
        risk_score=4,
        confidence_score=4,
        target_ids=["11", "12"],
        params={
            "product_id": 1,
            "updates": [
                {
                    "variant_id": 11,
                    "current_price": "10.00",
                    "current_stock": 1,
                    "price": "12.00",
                    "stock": 1,
                },
                {
                    "variant_id": 12,
                    "current_price": "10.00",
                    "current_stock": 2,
                    "price": "12.00",
                    "stock": 2,
                },
            ],
        },
    )
    with patch("nube_agent.storeops.actions.variant_updates.request") as mocked_request:
        diffs = apply_bulk_variant_update(action, dry_run=True)
    assert len(diffs) == 2
    mocked_request.assert_not_called()


def test_high_risk_bulk_variant_update_requires_confirmation_code():
    action = PlannedAction(
        action_id="action-2",
        action_type="bulk_variant_update",
        title="High-risk bulk variant update",
        summary="Apply several pricing changes.",
        impact_score=5,
        risk_score=4,
        confidence_score=4,
        target_ids=["21", "22", "23"],
        params={
            "product_id": 1,
            "updates": [
                {
                    "variant_id": 21,
                    "current_price": "10.00",
                    "current_stock": 1,
                    "price": "13.00",
                    "stock": 1,
                },
                {
                    "variant_id": 22,
                    "current_price": "10.00",
                    "current_stock": 1,
                    "price": "13.00",
                    "stock": 1,
                },
                {
                    "variant_id": 23,
                    "current_price": "10.00",
                    "current_stock": 1,
                    "price": "13.00",
                    "stock": 1,
                },
            ],
        },
        high_risk=True,
        confirmation_code="PRICE-02",
    )
    plan = ActionPlan(
        plan_id="plan-policy",
        audit_id="audit-policy",
        summary="Test plan",
        report_path="/reports/test.md",
        findings=[],
        actions=[action],
    )

    with TemporaryDirectory() as tmp_dir:
        fs = VirtualFilesystem(store=FileBackedStore(Path(tmp_dir)))
        with (
            patch("nube_agent.storeops.memory.get_virtual_filesystem", return_value=fs),
            patch(
                "nube_agent.storeops.audit_runner._apply_action",
                side_effect=AssertionError("should not execute"),
            ),
        ):
            save_plan(plan)
            result = apply_saved_plan(
                plan.plan_id,
                dry_run=False,
                approved_action_ids={action.action_id},
                confirmation_codes={},
            )

    assert action.action_id in result.blocked_actions
