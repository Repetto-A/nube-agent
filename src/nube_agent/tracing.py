"""LangSmith tracing helpers for StoreOps flows."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Iterator

from langsmith.run_helpers import tracing_context

from nube_agent.config import LANGSMITH_PROJECT, LANGSMITH_TRACING


@contextmanager
def trace_storeops_run(
    *,
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> Iterator[None]:
    if not LANGSMITH_TRACING:
        with nullcontext():
            yield
        return

    with tracing_context(
        project_name=LANGSMITH_PROJECT,
        tags=tags or [],
        metadata=metadata or {},
        enabled=True,
    ):
        yield
