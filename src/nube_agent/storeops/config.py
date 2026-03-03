"""StoreOps-specific configuration helpers."""

from dataclasses import dataclass

from nube_agent.config import (
    STOREOPS_ABANDONED_CHECKOUT_LOOKBACK_DAYS,
    STOREOPS_BEST_SELLER_LOOKBACK_DAYS,
    STOREOPS_CONFIRMATION_REQUIRED_PRICE_DELTA_PCT,
    STOREOPS_CONFIRMATION_REQUIRED_VARIANT_COUNT,
    STOREOPS_DESCRIPTION_MIN_CHARS,
    STOREOPS_MIN_IMAGE_COUNT,
    STOREOPS_TITLE_MIN_CHARS,
)


@dataclass(slots=True, frozen=True)
class StoreOpsThresholds:
    min_image_count: int = STOREOPS_MIN_IMAGE_COUNT
    title_min_chars: int = STOREOPS_TITLE_MIN_CHARS
    description_min_chars: int = STOREOPS_DESCRIPTION_MIN_CHARS
    best_seller_lookback_days: int = STOREOPS_BEST_SELLER_LOOKBACK_DAYS
    abandoned_checkout_lookback_days: int = STOREOPS_ABANDONED_CHECKOUT_LOOKBACK_DAYS
    confirmation_price_delta_pct: float = STOREOPS_CONFIRMATION_REQUIRED_PRICE_DELTA_PCT
    confirmation_variant_count: int = STOREOPS_CONFIRMATION_REQUIRED_VARIANT_COUNT
