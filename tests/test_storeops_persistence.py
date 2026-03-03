from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nube_agent.persistence.file_store import FileBackedStore
from nube_agent.persistence.repositories import VirtualFilesystem
from nube_agent.storeops.memory import LAST_AUDIT_PATH, save_last_audit
from nube_agent.storeops.models import ActionPlan, ExecutionDecision


def test_latest_audit_memory_persists_required_fields():
    plan = ActionPlan(
        plan_id="plan-memory",
        audit_id="audit-memory",
        summary="Memory summary",
        report_path="/reports/test.md",
        findings=[],
        actions=[],
    )
    decisions = [ExecutionDecision(action_id="action-1", decision="approved", reason="approved")]

    with TemporaryDirectory() as tmp_dir:
        fs = VirtualFilesystem(store=FileBackedStore(Path(tmp_dir)))
        with patch("nube_agent.storeops.memory.get_virtual_filesystem", return_value=fs):
            save_last_audit(plan, decisions=decisions)
            payload = fs.read_json(LAST_AUDIT_PATH)

    assert payload["issues_found"] == 0
    assert "recommended_actions" in payload
    assert "user_decisions" in payload
    assert "timestamps" in payload
