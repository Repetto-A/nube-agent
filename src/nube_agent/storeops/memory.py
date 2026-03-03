from __future__ import annotations

from datetime import UTC, datetime

from nube_agent.persistence.repositories import get_virtual_filesystem
from nube_agent.storeops.models import ActionPlan, ExecutionDecision, MemorySummary

LAST_AUDIT_PATH = "/memories/storeops/last_audit.json"


def _plan_path(plan_id: str) -> str:
    return f"/memories/storeops/plans/{plan_id}.json"


def _report_path() -> str:
    return f"/reports/{datetime.now(UTC).date().isoformat()}_audit.md"


def save_plan(plan: ActionPlan) -> str:
    fs = get_virtual_filesystem()
    path = _plan_path(plan.plan_id)
    fs.write_json(path, plan.model_dump(mode="json"))
    return path


def load_plan(plan_id: str) -> ActionPlan:
    fs = get_virtual_filesystem()
    payload = fs.read_json(_plan_path(plan_id))
    if payload is None:
        raise FileNotFoundError(f"Plan {plan_id} not found")
    return ActionPlan.model_validate(payload)


def load_latest_plan() -> ActionPlan:
    fs = get_virtual_filesystem()
    payload = fs.read_json(LAST_AUDIT_PATH)
    if payload is None:
        raise FileNotFoundError("No prior StoreOps audit found")
    return load_plan(payload["plan_id"])


def save_last_audit(
    plan: ActionPlan,
    *,
    decisions: list[ExecutionDecision] | None = None,
) -> str:
    fs = get_virtual_filesystem()
    summary = MemorySummary(
        audit_id=plan.audit_id,
        plan_id=plan.plan_id,
        issues_found=len(plan.findings),
        recommended_actions=[action.action_id for action in plan.actions],
        user_decisions=decisions or [],
        timestamps={
            "created_at": plan.created_at,
            "updated_at": datetime.now(UTC).isoformat(),
        },
        latest_report_path=plan.report_path,
    )
    fs.write_json(LAST_AUDIT_PATH, summary.model_dump(mode="json"))
    return LAST_AUDIT_PATH


def write_report(report_path: str, markdown: str) -> None:
    fs = get_virtual_filesystem()
    fs.write_text(report_path, markdown)


def resolve_report_path() -> str:
    return _report_path()
