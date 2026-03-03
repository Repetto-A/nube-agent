from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from nube_agent.storeops.config import StoreOpsThresholds
from nube_agent.storeops.models import AuditEvidence, AuditFinding

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _text_length(value: Any) -> int:
    if isinstance(value, dict):
        text = " ".join(str(item or "") for item in value.values())
    else:
        text = str(value or "")
    stripped = _HTML_TAG_RE.sub(" ", text)
    return len(" ".join(stripped.split()))


def _localized_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key, val in value.items() if val}
    return set()


def _product_name(product: dict[str, Any]) -> str:
    name = product.get("name", "")
    if isinstance(name, dict):
        return next((str(val) for val in name.values() if val), "Untitled product")
    return str(name or "Untitled product")


def _to_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_created_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_catalog_checks(
    snapshot: dict[str, Any],
    thresholds: StoreOpsThresholds,
) -> list[AuditFinding]:
    products = snapshot.get("products", [])
    categories = snapshot.get("categories", [])
    pages = snapshot.get("pages", [])
    orders = snapshot.get("orders", [])
    findings: list[AuditFinding] = []

    low_image_products = [
        product
        for product in products
        if len(product.get("images", [])) < thresholds.min_image_count
    ]
    if low_image_products:
        findings.append(
            AuditFinding(
                issue_id="catalog-low-images",
                issue_type="catalog.low_images",
                title="Products with too few images",
                summary=(
                    f"{len(low_image_products)} products have fewer than "
                    f"{thresholds.min_image_count} images."
                ),
                severity="medium",
                impact_score=4,
                risk_score=1,
                confidence_score=5,
                evidence=[
                    AuditEvidence(
                        source="products",
                        resource_type="product",
                        resource_id=str(product.get("id")),
                        message=(
                            f"{_product_name(product)} has "
                            f"{len(product.get('images', []))} images."
                        ),
                    )
                    for product in low_image_products[:10]
                ],
                resource_ids=[str(product.get("id")) for product in low_image_products],
            )
        )

    weak_content = []
    for product in products:
        title_len = _text_length(product.get("name"))
        desc_len = _text_length(product.get("description"))
        if title_len < thresholds.title_min_chars or desc_len < thresholds.description_min_chars:
            weak_content.append((product, title_len, desc_len))

    if weak_content:
        findings.append(
            AuditFinding(
                issue_id="catalog-weak-content",
                issue_type="catalog.weak_content",
                title="Weak product copy",
                summary=f"{len(weak_content)} products have short titles or descriptions.",
                severity="medium",
                impact_score=4,
                risk_score=2,
                confidence_score=4,
                evidence=[
                    AuditEvidence(
                        source="products",
                        resource_type="product",
                        resource_id=str(product.get("id")),
                        message=(
                            f"{_product_name(product)} title length={title_len}, "
                            f"description length={desc_len}."
                        ),
                    )
                    for product, title_len, desc_len in weak_content[:10]
                ],
                resource_ids=[str(product.get("id")) for product, _, _ in weak_content],
            )
        )

    price_anomalies: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for product in products:
        variants = product.get("variants", []) or []
        prices = [_to_float(variant.get("price")) for variant in variants]
        valid_prices = [price for price in prices if price is not None]
        if not valid_prices:
            continue
        baseline = median(valid_prices)
        for variant in variants:
            price = _to_float(variant.get("price"))
            if price is None:
                continue
            if price == 0:
                price_anomalies.append((product, variant, "zero_price"))
                continue
            if baseline and abs(price - baseline) / baseline >= 0.35:
                price_anomalies.append((product, variant, "inconsistent_price"))

    if price_anomalies:
        findings.append(
            AuditFinding(
                issue_id="catalog-price-anomalies",
                issue_type="catalog.variant_pricing",
                title="Variant pricing anomalies",
                summary=f"{len(price_anomalies)} variants have zero or inconsistent pricing.",
                severity="high",
                impact_score=5,
                risk_score=3,
                confidence_score=4,
                evidence=[
                    AuditEvidence(
                        source="variants",
                        resource_type="variant",
                        resource_id=str(variant.get("id")),
                        message=(
                            f"{_product_name(product)} variant {variant.get('id')} "
                            f"flagged for {reason} with price={variant.get('price')}."
                        ),
                        details={"product_id": product.get("id")},
                    )
                    for product, variant, reason in price_anomalies[:10]
                ],
                resource_ids=[str(variant.get("id")) for _, variant, _ in price_anomalies],
            )
        )

    lookback_start = datetime.now(UTC) - timedelta(days=thresholds.best_seller_lookback_days)
    units_by_product: Counter[str] = Counter()
    for order in orders:
        created_at = _parse_created_at(order.get("created_at"))
        if created_at is not None and created_at < lookback_start:
            continue
        for item in order.get("products", []) or order.get("line_items", []) or []:
            product_id = item.get("product_id") or item.get("id")
            if product_id is None:
                continue
            units_by_product[str(product_id)] += _to_int(item.get("quantity"), 1)

    low_stock_products: list[tuple[dict[str, Any], int, int]] = []
    for product in products:
        sold_units = units_by_product.get(str(product.get("id")), 0)
        if sold_units <= 0:
            continue
        total_stock = sum(
            _to_int(variant.get("stock"), 0) for variant in product.get("variants", [])
        )
        if total_stock <= 1:
            low_stock_products.append((product, sold_units, total_stock))

    if low_stock_products:
        findings.append(
            AuditFinding(
                issue_id="catalog-best-seller-stock",
                issue_type="catalog.low_stock_best_seller",
                title="Best sellers are low on stock",
                summary=(
                    f"{len(low_stock_products)} best-selling products are "
                    "at or near zero stock."
                ),
                severity="high",
                impact_score=5,
                risk_score=3,
                confidence_score=4,
                evidence=[
                    AuditEvidence(
                        source="orders",
                        resource_type="product",
                        resource_id=str(product.get("id")),
                        message=(
                            f"{_product_name(product)} sold {sold_units} units recently "
                            f"but has stock={stock}."
                        ),
                    )
                    for product, sold_units, stock in low_stock_products[:10]
                ],
                resource_ids=[str(product.get("id")) for product, _, _ in low_stock_products],
            )
        )

    category_counts: Counter[str] = Counter()
    uncategorized_products: list[dict[str, Any]] = []
    for product in products:
        category_ids: list[str] = []
        raw_categories = product.get("categories") or []
        for category in raw_categories:
            if isinstance(category, dict):
                if category.get("id") is not None:
                    category_ids.append(str(category["id"]))
            else:
                category_ids.append(str(category))
        if not category_ids:
            uncategorized_products.append(product)
        category_counts.update(category_ids)

    empty_categories = [
        category for category in categories if category_counts[str(category.get("id"))] == 0
    ]
    if empty_categories or uncategorized_products:
        evidence = []
        for category in empty_categories[:5]:
            evidence.append(
                AuditEvidence(
                    source="categories",
                    resource_type="category",
                    resource_id=str(category.get("id")),
                    message=f"Category {category.get('id')} has no assigned products.",
                )
            )
        for product in uncategorized_products[:5]:
            evidence.append(
                AuditEvidence(
                    source="products",
                    resource_type="product",
                    resource_id=str(product.get("id")),
                    message=f"{_product_name(product)} is missing category assignments.",
                )
            )
        findings.append(
            AuditFinding(
                issue_id="catalog-orphan-categories",
                issue_type="catalog.orphan_categories",
                title="Orphan categories or uncategorized products",
                summary=(
                    f"{len(empty_categories)} categories are empty and "
                    f"{len(uncategorized_products)} products have no categories."
                ),
                severity="medium",
                impact_score=3,
                risk_score=2,
                confidence_score=5,
                evidence=evidence,
                resource_ids=[
                    *[str(category.get("id")) for category in empty_categories],
                    *[str(product.get("id")) for product in uncategorized_products],
                ],
            )
        )

    locale_usage: Counter[str] = Counter()
    for product in products:
        locale_usage.update(_localized_keys(product.get("name")))
        locale_usage.update(_localized_keys(product.get("description")))
    for page in pages:
        page_i18n = page.get("page", {}).get("i18n") if isinstance(page.get("page"), dict) else None
        if isinstance(page_i18n, dict):
            locale_usage.update(page_i18n.keys())

    if len(locale_usage) > 1:
        missing_multilingual: list[tuple[str, str, str]] = []
        required_locales = set(locale_usage)
        for product in products:
            present = _localized_keys(product.get("name")) | _localized_keys(
                product.get("description")
            )
            if present and present != required_locales:
                missing = ",".join(sorted(required_locales - present))
                missing_multilingual.append(
                    (str(product.get("id")), _product_name(product), missing)
                )
        if missing_multilingual:
            findings.append(
                AuditFinding(
                    issue_id="catalog-multilingual-gaps",
                    issue_type="catalog.multilingual_content",
                    title="Missing multilingual content",
                    summary=(
                        f"{len(missing_multilingual)} products are missing "
                        "one or more locales."
                    ),
                    severity="medium",
                    impact_score=3,
                    risk_score=2,
                    confidence_score=4,
                    evidence=[
                        AuditEvidence(
                            source="products",
                            resource_type="product",
                            resource_id=product_id,
                            message=f"{name} is missing locales: {missing}.",
                        )
                        for product_id, name, missing in missing_multilingual[:10]
                    ],
                    resource_ids=[product_id for product_id, _, _ in missing_multilingual],
                )
            )

    return findings
