from nube_agent.storeops.models import ActionPlan, PlannedAction
from nube_agent.storeops.report_writer import build_report_sections, render_markdown_report


def test_report_writer_produces_required_sections():
    plan = ActionPlan(
        plan_id="plan-1",
        audit_id="audit-1",
        summary="Found several issues.",
        report_path="/reports/test.md",
        findings=[],
        actions=[
            PlannedAction(
                action_id="action-1",
                action_type="memory_note",
                title="Save note",
                summary="Persist a note.",
                impact_score=1,
                risk_score=1,
                confidence_score=5,
                target_ids=["/memories/storeops/preferences.json"],
                params={"path": "/memories/storeops/preferences.json", "note": {"summary": "ok"}},
            )
        ],
    )
    sections = build_report_sections(plan)
    markdown = render_markdown_report(plan, sections)

    assert "## Summary" in markdown
    assert "## Findings" in markdown
    assert "## Recommended Actions" in markdown
    assert "## Approvals Required" in markdown
    assert "## Execution Notes" in markdown
