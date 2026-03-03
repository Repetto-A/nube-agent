"""Local StoreOps evals for MVP safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import httpx

from nube_agent.persistence.file_store import FileBackedStore
from nube_agent.persistence.repositories import VirtualFilesystem
from nube_agent.storeops.audit_runner import apply_saved_plan
from nube_agent.storeops.fixtures import load_fixture_scenarios
from nube_agent.storeops.memory import save_plan
from nube_agent.storeops.models import ActionPlan, PlannedAction


@dataclass(slots=True)
class EvalOutcome:
    name: str
    passed: bool
    detail: str


def _build_plan(action: PlannedAction) -> ActionPlan:
    return ActionPlan(
        plan_id=f"eval-{action.action_id}",
        audit_id="audit-eval",
        summary="Fixture plan",
        report_path="/reports/eval.md",
        findings=[],
        actions=[action],
    )


def run_dry_run_purity_eval() -> list[EvalOutcome]:
    outcomes: list[EvalOutcome] = []
    scenarios = load_fixture_scenarios()
    for scenario in scenarios:
        action = PlannedAction.model_validate(scenario["action"])
        plan = _build_plan(action)
        with TemporaryDirectory() as tmp_dir:
            store = FileBackedStore(Path(tmp_dir))
            fs = VirtualFilesystem(store=store)

            def fake_http_request(method: str, url: str, **kwargs: Any):
                if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                    raise AssertionError("dry_run should not hit mutation HTTP methods")
                return httpx.Response(200, json={"main_language": "es", "country": "AR"})

            with (
                patch("nube_agent.storeops.memory.get_virtual_filesystem", return_value=fs),
                patch(
                    "nube_agent.persistence.repositories.get_virtual_filesystem", return_value=fs
                ),
                patch("nube_agent.api.httpx.request", side_effect=fake_http_request),
            ):
                save_plan(plan)
                result = apply_saved_plan(
                    plan.plan_id,
                    dry_run=True,
                    approved_action_ids={action.action_id},
                    confirmation_codes={action.action_id: action.confirmation_code or ""},
                )
        passed = bool(result.diffs)
        outcomes.append(
            EvalOutcome(
                name=scenario["name"],
                passed=passed,
                detail="dry_run returned diffs without HTTP mutation calls",
            )
        )
    return outcomes


def run_policy_compliance_eval() -> list[EvalOutcome]:
    outcomes: list[EvalOutcome] = []
    scenarios = load_fixture_scenarios()
    for scenario in scenarios:
        action = PlannedAction.model_validate(scenario["action"])
        plan = _build_plan(action)
        should_block = bool(scenario.get("expect_confirmation"))
        with TemporaryDirectory() as tmp_dir:
            store = FileBackedStore(Path(tmp_dir))
            fs = VirtualFilesystem(store=store)
            with (
                patch("nube_agent.storeops.memory.get_virtual_filesystem", return_value=fs),
                patch(
                    "nube_agent.persistence.repositories.get_virtual_filesystem", return_value=fs
                ),
            ):
                action_patch = (
                    patch(
                        "nube_agent.storeops.audit_runner._apply_action",
                        side_effect=AssertionError("blocked action attempted mutation"),
                    )
                    if should_block
                    else patch(
                        "nube_agent.storeops.audit_runner._apply_action",
                        return_value=[],
                    )
                )
                with action_patch:
                    save_plan(plan)
                    result = apply_saved_plan(
                        plan.plan_id,
                        dry_run=False,
                        approved_action_ids={action.action_id},
                        confirmation_codes={},
                    )
        passed = bool(result.blocked_actions) if should_block else not bool(result.blocked_actions)
        outcomes.append(
            EvalOutcome(
                name=scenario["name"],
                passed=passed,
                detail="high-risk action blocked without confirmation"
                if should_block
                else "low-risk action is eligible after approval",
            )
        )
    return outcomes


def main() -> None:
    groups = {
        "dry_run_purity": run_dry_run_purity_eval(),
        "policy_compliance": run_policy_compliance_eval(),
    }
    for group_name, outcomes in groups.items():
        print(group_name)
        for outcome in outcomes:
            status = "PASS" if outcome.passed else "FAIL"
            print(f"  {status} {outcome.name}: {outcome.detail}")


if __name__ == "__main__":
    main()
