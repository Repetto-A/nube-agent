from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from nube_agent.api import request, store_language
from nube_agent.config import TIENDANUBE_STORE_ID
from nube_agent.storeops.actions import (
    apply_bulk_variant_update,
    apply_coupon_change,
    apply_memory_note,
    apply_page_template_update,
    apply_product_copy_update,
    preview_bulk_variant_update,
    preview_coupon_change,
    preview_memory_note,
    preview_page_template_update,
    preview_product_copy_update,
)
from nube_agent.storeops.checks import run_catalog_checks, run_marketing_checks, run_order_checks
from nube_agent.storeops.config import StoreOpsThresholds
from nube_agent.storeops.memory import (
    load_latest_plan,
    load_plan,
    resolve_report_path,
    save_last_audit,
    save_plan,
    write_report,
)
from nube_agent.storeops.models import (
    ApplyResult,
    AuditContext,
    AuditRequest,
    AuditResult,
    ExecutionDecision,
    StructuredDiff,
)
from nube_agent.storeops.planner import build_action_plan
from nube_agent.storeops.report_writer import build_report_sections, render_markdown_report
from nube_agent.storeops.scoring import rank_findings
from nube_agent.tracing import trace_storeops_run


def _iso_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _fetch_paginated(
    path: str,
    *,
    per_page: int = 200,
    extra_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        params = {"page": page, "per_page": per_page}
        if extra_params:
            params.update(extra_params)
        result = request("GET", path, params=params)
        if not isinstance(result, list) or not result:
            break
        rows.extend(result)
        if len(result) < per_page:
            break
        page += 1
    return rows


def _collect_snapshot(thresholds: StoreOpsThresholds) -> dict[str, Any]:
    return {
        "store": request("GET", "/store"),
        "products": _fetch_paginated("/products"),
        "categories": _fetch_paginated("/categories"),
        "coupons": _fetch_paginated("/coupons"),
        "pages": _fetch_paginated("/pages", per_page=20),
        "orders": _fetch_paginated(
            "/orders",
            extra_params={"created_at_min": _iso_days_ago(thresholds.best_seller_lookback_days)},
        ),
        "checkouts": _fetch_paginated(
            "/checkouts",
            extra_params={
                "created_at_min": _iso_days_ago(thresholds.abandoned_checkout_lookback_days * 2)
            },
        ),
    }


def run_audit(request_model: AuditRequest | None = None) -> AuditResult:
    thresholds = StoreOpsThresholds()
    request_model = request_model or AuditRequest(
        store_id=TIENDANUBE_STORE_ID,
        dry_run=True,
        language=store_language(),
    )
    with trace_storeops_run(
        tags=[
            "storeops",
            "audit",
            "dry_run" if request_model.dry_run else "execute",
            "ops-auditor",
        ],
        metadata={
            "store_id": request_model.store_id,
            "mode": "dry_run" if request_model.dry_run else "execute",
            "agent": "ops-auditor",
            "action_type": "audit",
        },
    ):
        snapshot = _collect_snapshot(thresholds)
        context = AuditContext(request=request_model, raw_snapshot=snapshot)
        del context
        findings = rank_findings(
            run_catalog_checks(snapshot, thresholds)
            + run_marketing_checks(snapshot, thresholds)
            + run_order_checks(snapshot, thresholds)
        )
        report_path = resolve_report_path()
        plan = build_action_plan(
            findings,
            snapshot,
            report_path=report_path,
            dry_run=request_model.dry_run,
        )
        sections = build_report_sections(plan)
        write_report(report_path, render_markdown_report(plan, sections))
        save_plan(plan)
        memory_path = save_last_audit(plan)
        return AuditResult(
            plan=plan,
            report_sections=sections,
            report_path=report_path,
            memory_path=memory_path,
        )


def preview_saved_plan(plan_id: str | None = None) -> ApplyResult:
    plan = load_plan(plan_id) if plan_id else load_latest_plan()
    diffs: list[StructuredDiff] = []
    for action in plan.actions:
        diffs.extend(_preview_action(action))
    return ApplyResult(
        plan_id=plan.plan_id,
        dry_run=True,
        diffs=diffs,
        decisions=[
            ExecutionDecision(
                action_id=action.action_id,
                decision="previewed",
                reason="Dry-run preview generated.",
            )
            for action in plan.actions
        ],
        message=f"Generated {len(diffs)} diffs for plan {plan.plan_id}.",
    )


def apply_saved_plan(
    plan_id: str,
    *,
    dry_run: bool,
    confirmation_codes: dict[str, str] | None = None,
    approved_action_ids: set[str] | None = None,
) -> ApplyResult:
    plan = load_plan(plan_id)
    confirmation_codes = confirmation_codes or {}
    approved_action_ids = approved_action_ids or set()
    executed_actions: list[str] = []
    blocked_actions: list[str] = []
    decisions: list[ExecutionDecision] = []
    diffs: list[StructuredDiff] = []

    with trace_storeops_run(
        tags=["storeops", "apply", "dry_run" if dry_run else "execute", "ops-auditor"],
        metadata={
            "store_id": TIENDANUBE_STORE_ID,
            "mode": "dry_run" if dry_run else "execute",
            "agent": "ops-auditor",
            "action_type": "apply",
            "plan_id": plan.plan_id,
            "audit_id": plan.audit_id,
            "dry_run": dry_run,
        },
    ):
        for action in plan.actions:
            if action.action_id not in approved_action_ids:
                decisions.append(
                    ExecutionDecision(
                        action_id=action.action_id,
                        decision="rejected",
                        reason="Action not approved by the user.",
                    )
                )
                blocked_actions.append(action.action_id)
                continue

            if action.high_risk:
                expected = (action.confirmation_code or "").upper()
                provided = confirmation_codes.get(action.action_id, "").upper()
                if not expected or provided != expected:
                    decisions.append(
                        ExecutionDecision(
                            action_id=action.action_id,
                            decision="blocked",
                            reason="High-risk confirmation code was missing or incorrect.",
                            confirmation_code=confirmation_codes.get(action.action_id),
                        )
                    )
                    blocked_actions.append(action.action_id)
                    continue

            action_diffs = _apply_action(action, dry_run=dry_run)
            diffs.extend(action_diffs)
            decisions.append(
                ExecutionDecision(
                    action_id=action.action_id,
                    decision="previewed" if dry_run else "executed",
                    reason="Dry-run preview generated."
                    if dry_run
                    else "Action executed successfully.",
                    confirmation_code=confirmation_codes.get(action.action_id),
                )
            )
            if not dry_run:
                executed_actions.append(action.action_id)

        save_last_audit(plan, decisions=decisions)
        return ApplyResult(
            plan_id=plan.plan_id,
            dry_run=dry_run,
            diffs=diffs,
            decisions=decisions,
            executed_actions=executed_actions,
            blocked_actions=blocked_actions,
            message=f"Processed {len(plan.actions)} actions for plan {plan.plan_id}.",
        )


def _preview_action(action) -> list[StructuredDiff]:
    return {
        "product_copy_update": preview_product_copy_update,
        "bulk_variant_update": preview_bulk_variant_update,
        "coupon_update": preview_coupon_change,
        "page_update": preview_page_template_update,
        "memory_note": preview_memory_note,
    }[action.action_type](action)


def _apply_action(action, *, dry_run: bool) -> list[StructuredDiff]:
    return {
        "product_copy_update": apply_product_copy_update,
        "bulk_variant_update": apply_bulk_variant_update,
        "coupon_update": apply_coupon_change,
        "page_update": apply_page_template_update,
        "memory_note": apply_memory_note,
    }[action.action_type](action, dry_run=dry_run)
