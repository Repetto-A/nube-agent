from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AuditEvidence(BaseModel):
    source: str
    resource_type: str
    resource_id: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AuditFinding(BaseModel):
    issue_id: str
    issue_type: str
    title: str
    summary: str
    severity: Literal["low", "medium", "high", "critical"]
    impact_score: int = Field(ge=1, le=5)
    risk_score: int = Field(ge=1, le=5)
    confidence_score: int = Field(ge=1, le=5)
    evidence: list[AuditEvidence] = Field(default_factory=list)
    recommended_action_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)


class StructuredDiff(BaseModel):
    action_id: str
    target_type: str
    target_id: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    summary: str


class ApprovalChallenge(BaseModel):
    action_id: str
    code: str
    required: bool = True
    reason: str


class PlannedAction(BaseModel):
    action_id: str
    action_type: str
    title: str
    summary: str
    impact_score: int = Field(ge=1, le=5)
    risk_score: int = Field(ge=1, le=5)
    confidence_score: int = Field(ge=1, le=5)
    target_ids: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = True
    high_risk: bool = False
    confirmation_code: str | None = None
    confirmation_reason: str | None = None
    diff_preview: list[StructuredDiff] = Field(default_factory=list)
    status: Literal["planned", "previewed", "executed", "blocked"] = "planned"


class ActionPlan(BaseModel):
    plan_id: str
    audit_id: str
    created_at: str = Field(default_factory=utc_now_iso)
    summary: str
    dry_run: bool = True
    report_path: str
    findings: list[AuditFinding] = Field(default_factory=list)
    actions: list[PlannedAction] = Field(default_factory=list)


class ExecutionDecision(BaseModel):
    action_id: str
    decision: Literal["approved", "rejected", "blocked", "executed", "previewed", "skipped"]
    reason: str = ""
    confirmation_code: str | None = None
    timestamp: str = Field(default_factory=utc_now_iso)


class MemorySummary(BaseModel):
    audit_id: str
    plan_id: str
    issues_found: int
    recommended_actions: list[str] = Field(default_factory=list)
    user_decisions: list[ExecutionDecision] = Field(default_factory=list)
    timestamps: dict[str, str] = Field(default_factory=dict)
    latest_report_path: str


class ReportSections(BaseModel):
    summary: str
    findings: str
    recommended_actions: str
    approvals_required: str
    execution_notes: str


class AuditRequest(BaseModel):
    store_id: str
    dry_run: bool = True
    language: str = "es"
    thread_id: str | None = None
    lookback_days: int = 30
    generated_at: str = Field(default_factory=utc_now_iso)


class AuditContext(BaseModel):
    request: AuditRequest
    store_name: str | None = None
    raw_snapshot: dict[str, Any] = Field(default_factory=dict)


class AuditResult(BaseModel):
    plan: ActionPlan
    report_sections: ReportSections
    report_path: str
    memory_path: str


class ApplyResult(BaseModel):
    plan_id: str
    dry_run: bool
    diffs: list[StructuredDiff] = Field(default_factory=list)
    decisions: list[ExecutionDecision] = Field(default_factory=list)
    executed_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    message: str = ""
