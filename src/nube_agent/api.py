import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import Any

import httpx

from nube_agent.config import BASE_URL, TIENDANUBE_ACCESS_TOKEN, USER_AGENT

_MUTATION_FIREWALL: ContextVar[bool] = ContextVar("mutation_firewall", default=False)
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class MutationBlockedError(RuntimeError):
    """Raised when a dry-run context attempts to hit a mutation endpoint."""


def mutations_blocked() -> bool:
    return _MUTATION_FIREWALL.get()


@contextmanager
def mutation_firewall(enabled: bool = True):
    token = _MUTATION_FIREWALL.set(enabled)
    try:
        yield
    finally:
        _MUTATION_FIREWALL.reset(token)


def _headers() -> dict[str, str]:
    return {
        "Authentication": f"bearer {TIENDANUBE_ACCESS_TOKEN}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any] | str:
    """Make an HTTP request to the Tiendanube API.

    Returns parsed JSON on success, or a descriptive error string on failure.
    Retries once on 429 (rate limited).
    """
    method = method.upper()
    if mutations_blocked() and method in _MUTATION_METHODS:
        raise MutationBlockedError(
            f"Dry-run mutation firewall blocked {method} {path}"
        )

    url = f"{BASE_URL}{path}"

    for attempt in range(2):
        try:
            resp = httpx.request(
                method,
                url,
                headers=_headers(),
                params=params,
                json=json_body,
                timeout=30.0,
            )
        except httpx.TransportError as e:
            return f"HTTP error: {e}"

        if resp.status_code == 429 and attempt == 0:
            try:
                wait = float(resp.headers.get("Retry-After", "1"))
            except (ValueError, TypeError):
                wait = 1.0
            time.sleep(wait)
            continue

        if resp.status_code == 204:
            return {"status": "success", "message": "Resource deleted"}

        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            return f"API error {resp.status_code}: {detail}"

        try:
            return resp.json()
        except Exception:
            return resp.text

    return "Request failed after retry"


def to_json(result: Any) -> str:
    """Convert an API result to a JSON string for the LLM.

    Returns proper JSON for dicts/lists, or the raw string otherwise.
    """
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


@lru_cache(maxsize=1)
def _store_info() -> dict:
    """Fetch and cache the store info from the API."""
    raw = request("GET", "/store")
    if isinstance(raw, dict):
        return raw
    return {}


def store_language() -> str:
    """Return the store's main language code (e.g. 'es', 'pt', 'en')."""
    return _store_info().get("main_language", "es")


def store_locale() -> str:
    """Return the store's i18n locale key (e.g. 'es_AR', 'pt_BR')."""
    info = _store_info()
    lang = info.get("main_language", "es")
    country = info.get("country", "")
    return f"{lang}_{country}" if country else lang


def parse_json(raw: str, label: str = "input") -> dict | list | str:
    """Safely parse a JSON string from the LLM.

    Returns the parsed object on success, or a descriptive error string.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return f"Invalid JSON in {label}: {e}"
