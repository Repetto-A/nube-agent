from nube_agent.storeops.audit_runner import apply_saved_plan, preview_saved_plan


def preview_plan_apply(plan_id: str = "") -> str:
    """Preview a saved plan and return structured diffs without mutating the API."""
    result = preview_saved_plan(plan_id or None)
    return result.model_dump_json()


def apply_plan(plan_id: str, confirmation_code: str = "", dry_run: bool = False) -> str:
    """Apply a saved plan after CLI-managed approvals have been collected."""
    approved_action_ids: set[str] = set()
    confirmation_codes: dict[str, str] = {}
    if confirmation_code:
        approved_action_ids.add("__invalid__")
        confirmation_codes["__invalid__"] = confirmation_code
    result = apply_saved_plan(
        plan_id,
        dry_run=dry_run,
        confirmation_codes=confirmation_codes,
        approved_action_ids=approved_action_ids,
    )
    return result.model_dump_json()
