import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TIENDANUBE_ACCESS_TOKEN = os.environ.get("TIENDANUBE_ACCESS_TOKEN", "")
TIENDANUBE_STORE_ID = os.environ.get("TIENDANUBE_STORE_ID", "")

MODEL = "openai:gpt-4o"
USER_AGENT = os.environ.get("USER_AGENT", "Nube Agent")
BASE_URL = f"https://api.tiendanube.com/2025-03/{TIENDANUBE_STORE_ID}"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


LANGSMITH_TRACING = _env_bool("LANGSMITH_TRACING", False)
LANGSMITH_PROJECT = os.environ.get("LANGSMITH_PROJECT", "storeops-copilot")

STOREOPS_DATA_DIR = Path(os.environ.get("STOREOPS_DATA_DIR", ".storeops_data"))
STOREOPS_REPORTS_DIR = os.environ.get("STOREOPS_REPORTS_DIR", "/reports")
STOREOPS_CONFIRMATION_REQUIRED_PRICE_DELTA_PCT = float(
    os.environ.get("STOREOPS_CONFIRMATION_REQUIRED_PRICE_DELTA_PCT", "20")
)
STOREOPS_CONFIRMATION_REQUIRED_VARIANT_COUNT = int(
    os.environ.get("STOREOPS_CONFIRMATION_REQUIRED_VARIANT_COUNT", "3")
)
STOREOPS_BEST_SELLER_LOOKBACK_DAYS = int(
    os.environ.get("STOREOPS_BEST_SELLER_LOOKBACK_DAYS", "30")
)
STOREOPS_ABANDONED_CHECKOUT_LOOKBACK_DAYS = int(
    os.environ.get("STOREOPS_ABANDONED_CHECKOUT_LOOKBACK_DAYS", "14")
)
STOREOPS_MIN_IMAGE_COUNT = int(os.environ.get("STOREOPS_MIN_IMAGE_COUNT", "2"))
STOREOPS_TITLE_MIN_CHARS = int(os.environ.get("STOREOPS_TITLE_MIN_CHARS", "20"))
STOREOPS_DESCRIPTION_MIN_CHARS = int(
    os.environ.get("STOREOPS_DESCRIPTION_MIN_CHARS", "80")
)


def validate() -> None:
    """Validate that all required environment variables are set."""
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not TIENDANUBE_ACCESS_TOKEN:
        missing.append("TIENDANUBE_ACCESS_TOKEN")
    if not TIENDANUBE_STORE_ID:
        missing.append("TIENDANUBE_STORE_ID")
    if missing:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in the values."
        )
