from __future__ import annotations

from nube_agent.storeops.models import ActionPlan, ReportSections


def build_report_sections(plan: ActionPlan) -> ReportSections:
    findings_lines = []
    for finding in plan.findings:
        findings_lines.append(f"- {finding.title}: {finding.summary}")

    actions_lines = []
    approval_lines = []
    for action in plan.actions:
        actions_lines.append(
            f"- {action.title} ({action.action_type}): "
            f"impact={action.impact_score}, risk={action.risk_score}"
        )
        if action.high_risk and action.confirmation_code:
            approval_lines.append(
                f"- {action.title}: requires confirmation code `{action.confirmation_code}`"
            )
        else:
            approval_lines.append(f"- {action.title}: requires explicit approval")

    return ReportSections(
        summary=plan.summary,
        findings="\n".join(findings_lines) or "- No issues found",
        recommended_actions="\n".join(actions_lines) or "- No actions recommended",
        approvals_required="\n".join(approval_lines) or "- No approvals required",
        execution_notes=(
            "- Dry-run previews are non-mutating.\n"
            "- Apply mode records user decisions."
        ),
    )


def render_markdown_report(plan: ActionPlan, sections: ReportSections) -> str:
    return "\n".join(
        [
            "# StoreOps Audit",
            "",
            "## Summary",
            sections.summary,
            "",
            "## Findings",
            sections.findings,
            "",
            "## Recommended Actions",
            sections.recommended_actions,
            "",
            "## Approvals Required",
            sections.approvals_required,
            "",
            "## Execution Notes",
            sections.execution_notes,
            "",
            f"Plan ID: `{plan.plan_id}`",
            f"Audit ID: `{plan.audit_id}`",
        ]
    )
