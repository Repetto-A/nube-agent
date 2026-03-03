from datetime import UTC, datetime

from nube_agent.storeops.checks.catalog import run_catalog_checks
from nube_agent.storeops.config import StoreOpsThresholds
from nube_agent.storeops.evals import run_dry_run_purity_eval, run_policy_compliance_eval


def test_best_seller_stock_check_uses_orders_history():
    now = datetime.now(UTC).isoformat()
    snapshot = {
        "products": [
            {
                "id": 1,
                "name": {"es": "Remera Premium"},
                "description": {
                    "es": "Descripcion suficientemente larga para no disparar el chequeo de copy."
                },
                "images": [{"id": 1}, {"id": 2}],
                "variants": [{"id": 11, "stock": 0, "price": "10.00"}],
                "categories": [1],
            }
        ],
        "categories": [{"id": 1}],
        "pages": [],
        "orders": [{"created_at": now, "products": [{"product_id": 1, "quantity": 3}]}],
    }
    findings = run_catalog_checks(snapshot, StoreOpsThresholds())

    assert any(f.issue_type == "catalog.low_stock_best_seller" for f in findings)


def test_local_evals_run_against_mvp_fixtures():
    dry_run_results = run_dry_run_purity_eval()
    policy_results = run_policy_compliance_eval()

    assert len(dry_run_results) == 8
    assert len(policy_results) == 8
    assert all(result.passed for result in dry_run_results)
    assert all(result.passed for result in policy_results)
