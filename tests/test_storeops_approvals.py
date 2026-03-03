from nube_agent.subagents import SUBAGENTS


def test_interrupt_on_only_covers_truly_destructive_tools():
    catalog = next(agent for agent in SUBAGENTS if agent["name"] == "catalog-manager")
    marketing = next(agent for agent in SUBAGENTS if agent["name"] == "marketing-manager")
    orders = next(agent for agent in SUBAGENTS if agent["name"] == "order-manager")

    assert "bulk_update_stock_price" not in catalog.get("interrupt_on", {})
    assert catalog["interrupt_on"]["delete_product"] is True
    assert catalog["interrupt_on"]["delete_category"] is True
    assert orders["interrupt_on"]["cancel_order"] is True
    assert marketing["interrupt_on"]["delete_coupon"] is True
