from nube_agent.api import store_language
from nube_agent.config import TIENDANUBE_STORE_ID
from nube_agent.storeops.audit_runner import run_audit
from nube_agent.storeops.memory import load_latest_plan
from nube_agent.storeops.models import AuditRequest


def run_store_audit(dry_run: bool = True) -> str:
    """Run a StoreOps audit and return the saved plan and report metadata."""
    result = run_audit(
        AuditRequest(
            store_id=TIENDANUBE_STORE_ID,
            dry_run=dry_run,
            language=store_language(),
        )
    )
    return result.model_dump_json()


def get_latest_plan() -> str:
    """Load the latest saved StoreOps plan."""
    plan = load_latest_plan()
    return plan.model_dump_json()
