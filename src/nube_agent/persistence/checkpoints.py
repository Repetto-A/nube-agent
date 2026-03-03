"""Checkpoint helpers.

SQLite persistence is intentionally deferred to Phase 2. The MVP keeps the
current in-memory checkpointer and only persists StoreOps reports/memories.
"""

from langgraph.checkpoint.memory import MemorySaver


def build_checkpointer() -> MemorySaver:
    return MemorySaver()
