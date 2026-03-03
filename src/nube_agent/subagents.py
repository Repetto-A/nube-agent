from nube_agent.storeops.tools.audits import get_latest_plan, run_store_audit
from nube_agent.storeops.tools.execution import apply_plan, preview_plan_apply
from nube_agent.tools.abandoned_checkouts import (
    get_abandoned_checkout,
    list_abandoned_checkouts,
)
from nube_agent.tools.categories import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)
from nube_agent.tools.coupons import (
    create_coupon,
    delete_coupon,
    get_coupon,
    list_coupons,
    update_coupon,
)
from nube_agent.tools.customers import (
    create_customer,
    get_customer,
    list_customers,
    update_customer,
)
from nube_agent.tools.images import add_image, delete_image, list_images, update_image
from nube_agent.tools.orders import (
    cancel_order,
    close_order,
    get_order,
    list_orders,
    open_order,
    update_order,
)
from nube_agent.tools.pages import (
    create_page,
    delete_page,
    get_page,
    list_pages,
    update_page,
)
from nube_agent.tools.products import (
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
)
from nube_agent.tools.variants import (
    bulk_update_stock_price,
    create_variant,
    delete_variant,
    get_variant,
    list_variants,
    update_variant,
)

_PLAIN_TEXT_RULES = """\
You run inside a CLI terminal. Your output is rendered as plain text with no \
markdown renderer. Markdown syntax (**, ##, ```, [], -, *) will display as raw \
characters and look broken.

Output rules:
- Write in plain text only. Use line breaks and indentation for structure.
- Use UPPERCASE or "quotes" for emphasis instead of bold/italic.
- For structured data, use indented key-value layouts (Name: value).
- When listing resources, show a concise summary (name, key fields, status). \
Do not fetch or display nested/related resources unless the user explicitly asks.
- Respond in the same language the user writes in.

Operational rules:
- All store data is in the Tiendanube API. Use only the API tools provided.
- Before updating or deleting a resource by name, always look it up first \
(list or get) to find the correct ID. Never guess or fabricate IDs.
- Only perform the exact action the user requested. Do not carry over, \
queue, or repeat actions from previous messages."""

SUBAGENTS = [
    {
        "name": "catalog-manager",
        "description": (
            "Manages the product catalog via the Tiendanube API: list, view, create, "
            "update, and delete products, categories, variants, and images. "
            "Use when the user asks about products, stock, prices, categories, or images."
        ),
        "system_prompt": (
            f"You are the catalog manager for a Tiendanube store.\n{_PLAIN_TEXT_RULES}\n\n"
            "Key rules:\n"
            "- Prices and stock are on VARIANTS, not on products.\n"
            "- When creating products, remind the user about variant pricing.\n"
            "- Adding options to an existing product is a 3-step process: "
            "add attributes, update existing variant values, then create new variants.\n"
            "- When listing products or categories, show a short summary per item "
            "(name, price, stock, status). Do not include full descriptions, "
            "image URLs, or variant details unless asked.\n"
            "- Destructive actions (delete) are gated by the system. "
            "Just call the tool directly when asked."
        ),
        "tools": [
            list_products, get_product, create_product, update_product, delete_product,
            list_categories, get_category, create_category, update_category, delete_category,
            list_variants, get_variant, create_variant, update_variant, delete_variant,
            bulk_update_stock_price,
            list_images, add_image, update_image, delete_image,
        ],
        "interrupt_on": {
            "delete_product": True,
            "delete_category": True,
            "delete_variant": True,
            "delete_image": True,
        },
        "skills": [
            "skills/product-management/",
            "skills/category-management/",
            "skills/troubleshooting/",
        ],
    },
    {
        "name": "order-manager",
        "description": (
            "Manages orders via the Tiendanube API: list, view, update notes, close, "
            "reopen, and cancel orders. Use when the user asks about orders, sales, "
            "or shipping status."
        ),
        "system_prompt": (
            f"You are the order manager for a Tiendanube store.\n{_PLAIN_TEXT_RULES}\n\n"
            "Key rules:\n"
            "- Orders are read-heavy. You can update owner_note, close, reopen, or cancel.\n"
            "- Cancel is gated by the system. Just call cancel_order directly when asked.\n"
            "- Use filters (status, payment_status, shipping_status, q) to find orders.\n"
            "- When listing orders, show a concise summary per order "
            "(number, customer, total, status). Do not include full line items "
            "or addresses unless asked."
        ),
        "tools": [
            list_orders, get_order, update_order, close_order, open_order, cancel_order,
        ],
        "interrupt_on": {"cancel_order": True},
        "skills": ["skills/order-management/", "skills/troubleshooting/"],
    },
    {
        "name": "customer-manager",
        "description": (
            "Manages customers via the Tiendanube API: list, search, view, create, and "
            "update customer profiles. Use when the user asks about customers or contacts."
        ),
        "system_prompt": (
            f"You are the customer manager for a Tiendanube store.\n{_PLAIN_TEXT_RULES}\n\n"
            "Key rules:\n"
            "- Customers with orders cannot be deleted.\n"
            "- total_spent and accepts_marketing are read-only.\n"
            "- Use the note field for CRM tags and internal info.\n"
            "- When listing customers, show name, email, and total_spent. "
            "Do not include full addresses unless asked."
        ),
        "tools": [
            list_customers, get_customer, create_customer, update_customer,
        ],
        "skills": ["skills/customer-management/", "skills/troubleshooting/"],
    },
    {
        "name": "marketing-manager",
        "description": (
            "Manages marketing via the Tiendanube API: discount coupons (create, update, "
            "delete) and abandoned checkout recovery. Use when the user asks about "
            "coupons, discounts, promotions, or abandoned carts."
        ),
        "system_prompt": (
            f"You are the marketing manager for a Tiendanube store.\n{_PLAIN_TEXT_RULES}\n\n"
            "Key rules:\n"
            "- Coupon types: percentage, absolute, shipping.\n"
            "- Abandoned checkouts are read-only. Share the recovery URL "
            "with the customer.\n"
            "- When listing coupons, show code, type, value, and status. "
            "Do not include full restriction details unless asked.\n"
            "- Destructive actions (delete) are gated by the system. "
            "Just call the tool directly when asked."
        ),
        "tools": [
            list_coupons, get_coupon, create_coupon, update_coupon, delete_coupon,
            list_abandoned_checkouts, get_abandoned_checkout,
        ],
        "interrupt_on": {"delete_coupon": True},
        "skills": [
            "skills/coupon-management/",
            "skills/abandoned-checkouts/",
            "skills/troubleshooting/",
        ],
    },
    {
        "name": "content-manager",
        "description": (
            "Manages content pages via the Tiendanube API: list, view, create, update, "
            "and delete static pages (About Us, FAQ, Terms, etc.). Use when the user "
            "asks about pages or site content."
        ),
        "system_prompt": (
            f"You are the content manager for a Tiendanube store.\n{_PLAIN_TEXT_RULES}\n\n"
            "Key rules:\n"
            "- Page content supports HTML.\n"
            "- All text fields are multilingual, use the user language key.\n"
            "- When listing pages, show title and handle. Do not include "
            "full HTML content unless asked.\n"
            "- Destructive actions (delete) are gated by the system. "
            "Just call the tool directly when asked."
        ),
        "tools": [
            list_pages, get_page, create_page, update_page, delete_page,
        ],
        "interrupt_on": {"delete_page": True},
        "skills": ["skills/page-management/", "skills/troubleshooting/"],
    },
    {
        "name": "ops-auditor",
        "description": (
            "Runs StoreOps audits, prepares ranked action plans, previews dry-run diffs, "
            "and coordinates safe plan execution."
        ),
        "system_prompt": (
            f"You are the StoreOps ops-auditor for a Tiendanube store.\n{_PLAIN_TEXT_RULES}\n\n"
            "Key rules:\n"
            "- Build audit findings from API evidence, not guesses.\n"
            "- No destructive or high-risk action without approval.\n"
            "- Dry-run previews must never mutate the API.\n"
            "- Bulk or high-risk actions require a typed confirmation code handled by the CLI.\n"
            "- Save reports under /reports and summary memory under /memories/storeops.\n"
        ),
        "tools": [
            run_store_audit,
            get_latest_plan,
            preview_plan_apply,
            apply_plan,
        ],
        "skills": ["skills/troubleshooting/"],
    },
]
