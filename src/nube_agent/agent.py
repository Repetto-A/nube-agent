from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

from nube_agent.config import MODEL
from nube_agent.persistence import build_checkpointer, get_store
from nube_agent.prompts import load_system_prompt
from nube_agent.subagents import SUBAGENTS
from nube_agent.tools.store import get_store_info


def _make_backend(runtime):
    """Create a CompositeBackend that routes virtual paths to the file-backed store."""
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/memories/": StoreBackend(runtime, namespace=lambda _ctx: ("filesystem",)),
            "/reports/": StoreBackend(runtime, namespace=lambda _ctx: ("filesystem",)),
        },
    )


def build_agent():
    """Create and return the deep agent with sub-agents, HITL, and StoreOps storage."""
    store = get_store()
    checkpointer = build_checkpointer()
    agent = create_deep_agent(
        model=MODEL,
        tools=[get_store_info],
        system_prompt=load_system_prompt(),
        skills=["skills/store-overview/", "skills/troubleshooting/"],
        subagents=SUBAGENTS,
        backend=_make_backend,
        store=store,
        checkpointer=checkpointer,
    )
    return agent
