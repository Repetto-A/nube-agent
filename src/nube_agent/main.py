import argparse
import itertools
import json
import re
import shutil
import sys
import threading
import time
import uuid
from importlib.metadata import PackageNotFoundError, version

from langchain_core.messages import AIMessageChunk, ToolMessage
from langgraph.types import Command

from nube_agent.agent import build_agent
from nube_agent.api import store_language
from nube_agent.config import MODEL, TIENDANUBE_STORE_ID, validate
from nube_agent.storeops.audit_runner import apply_saved_plan, preview_saved_plan, run_audit
from nube_agent.storeops.memory import load_latest_plan, load_plan
from nube_agent.storeops.models import ActionPlan, ApplyResult, AuditRequest, StructuredDiff

try:
    VERSION = version("nube-agent")
except PackageNotFoundError:
    VERSION = "0.1.0"

BLUE = "\033[38;2;2;156;220m"
DARK = "\033[38;2;44;51;87m"
WHITE = "\033[38;2;255;255;255m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Debug palette
CYAN = "\033[38;2;2;156;220m"
YELLOW = "\033[38;2;255;193;7m"
GREEN = "\033[38;2;76;175;80m"
RED = "\033[38;2;244;67;54m"
GRAY = "\033[38;2;130;130;130m"


class Spinner:
    """Animated spinner for background work."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Thinking"):
        self.message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self) -> None:
        frames = itertools.cycle(self.FRAMES)
        while not self._stop.is_set():
            frame = next(frames)
            sys.stderr.write(f"\r{BLUE}{frame}{RESET} {DIM}{self.message}{RESET}   ")
            sys.stderr.flush()
            time.sleep(0.08)
        sys.stderr.write(f"\r{' ' * (len(self.message) + 10)}\r")
        sys.stderr.flush()

    def update(self, message: str) -> None:
        self.message = message

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def visible_len(s: str) -> int:
    """Length of string ignoring ANSI escape codes."""
    return len(_ANSI_RE.sub("", s))


def term_width() -> int:
    return min(shutil.get_terminal_size().columns, 80)


def box_line(text: str, width: int) -> str:
    """Create a line inside a box, padding correctly despite ANSI codes."""
    inner = width - 4  # account for "│ " and " │"
    pad = inner - visible_len(text)
    if pad < 0:
        pad = 0
    return f"{BLUE}│{RESET} {text}{' ' * pad} {BLUE}│{RESET}"


def print_banner(store_name: str, store_domain: str, store_currency: str) -> None:
    w = term_width()
    inner = w - 4
    top_label = f" Nube Agent v{VERSION} "
    # Top border with centered label
    border_left = (inner - len(top_label)) // 2
    border_right = inner - border_left - len(top_label)
    print(f"{BLUE}╭{'─' * border_left}{BOLD}{top_label}{RESET}{BLUE}{'─' * border_right}╮{RESET}")

    print(box_line("", w))
    print(box_line(f"  ☁  Welcome to {BOLD}{WHITE}Nube Agent{RESET}", w))
    print(box_line("", w))

    model_short = MODEL.split(":")[-1] if ":" in MODEL else MODEL
    print(box_line(f"  Store    {BOLD}{WHITE}{store_name}{RESET}", w))
    print(box_line(f"  Model    {DIM}{model_short}{RESET}", w))
    print(box_line(f"  Domain   {DIM}{store_domain}{RESET}", w))
    print(box_line(f"  Currency {DIM}{store_currency}{RESET}", w))
    print(box_line("", w))

    # Separator
    print(f"{BLUE}├{'─' * (w - 2)}┤{RESET}")

    # Commands section
    print(box_line(f"  {BLUE}Commands{RESET}", w))
    commands = [
        ("/store", "Show store info"),
        ("/audit", "Run StoreOps audit"),
        ("/plan", "Show latest plan"),
        ("/dry-run", "Preview diffs"),
        ("/apply <id>", "Apply a plan"),
        ("/products", "List products"),
        ("/orders", "List orders"),
        ("/customers", "List customers"),
        ("/coupons", "List coupons"),
        ("/categories", "List categories"),
        ("/abandoned", "Abandoned carts"),
        ("/pages", "Content pages"),
        ("/debug", "Toggle debug"),
        ("/help", "All commands"),
        ("/exit", "Exit"),
    ]
    for cmd, desc in commands:
        print(box_line(f"  {WHITE}{cmd:<14}{RESET}{DIM}{desc}{RESET}", w))

    print(box_line("", w))
    print(f"{BLUE}╰{'─' * (w - 2)}╯{RESET}")
    print()


def print_help() -> None:
    print(f"\n{BLUE}{BOLD}Commands{RESET}")
    print(f"{BLUE}{'─' * 40}{RESET}")
    commands = [
        ("/store", "Show store information"),
        ("/audit", "Run a StoreOps audit"),
        ("/plan", "Show the latest saved StoreOps plan"),
        ("/dry-run [plan_id]", "Preview plan changes without mutations"),
        ("/apply <plan_id>", "Apply a saved StoreOps plan"),
        ("/products", "List all products"),
        ("/orders", "List recent orders"),
        ("/customers", "List recent customers"),
        ("/coupons", "List discount coupons"),
        ("/categories", "List all categories"),
        ("/variants <id>", "List variants for a product"),
        ("/abandoned", "List abandoned checkouts"),
        ("/pages", "List content pages"),
        ("/debug", "Toggle debug mode on/off"),
        ("/clear", "Clear the screen"),
        ("/help", "Show this help message"),
        ("/exit, /quit", "Exit the agent"),
    ]
    for cmd, desc in commands:
        print(f"  {WHITE}{cmd:<20}{RESET} {DIM}{desc}{RESET}")
    print(f"\n{DIM}  Or just type naturally — the agent understands free-form requests.{RESET}\n")


def format_json_debug(data: str, max_len: int = 300) -> str:
    try:
        parsed = json.loads(data)
        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        formatted = data
    if len(formatted) > max_len:
        return formatted[:max_len] + f"\n    {DIM}... ({len(formatted)} chars total){RESET}"
    return formatted


def fetch_store_summary() -> tuple[str, str, str]:
    """Fetch store name, domain, and currency for the banner."""
    try:
        from nube_agent.api import request, store_language

        result = request("GET", "/store")
        if isinstance(result, dict):
            lang = store_language()
            name = result.get("name", {}).get(lang, "Unknown")
            domain = result.get("original_domain", "unknown")
            currency = result.get("main_currency", "?")
            return name, domain, currency
    except Exception:
        pass
    return "Unknown", "unknown", "?"


SHORTCUTS: dict[str, str] = {
    "/store": "Show me the store information",
    "/products": "List all my products with a summary",
    "/categories": "List all categories",
    "/orders": "List my recent orders with a summary",
    "/customers": "List my recent customers",
    "/coupons": "List all my discount coupons",
    "/abandoned": "List abandoned checkouts",
    "/pages": "List all content pages",
}


def handle_slash(user_input: str) -> str | None:
    """Handle slash commands. Returns a prompt to send to the agent,
    or None if the command was handled locally."""
    cmd = user_input.split()[0].lower()
    args = user_input[len(cmd) :].strip()

    if cmd in ("/exit", "/quit"):
        return "__EXIT__"
    if cmd == "/help":
        print_help()
        return None
    if cmd == "/clear":
        print("\033[2J\033[H", end="", flush=True)
        return None
    if cmd == "/debug":
        return "__TOGGLE_DEBUG__"
    if cmd == "/variants":
        if args:
            return f"List all variants for product ID {args}"
        return "List variants for all my products"

    if cmd in SHORTCUTS:
        return SHORTCUTS[cmd]

    print(f"  {DIM}Unknown command: {cmd}. Type /help for available commands.{RESET}")
    return None


def _print_storeops_plan(plan: ActionPlan) -> None:
    print(f"\n{BLUE}{BOLD}StoreOps Plan{RESET}")
    print(f"  Plan ID:    {WHITE}{plan.plan_id}{RESET}")
    print(f"  Audit ID:   {DIM}{plan.audit_id}{RESET}")
    print(f"  Report:     {DIM}{plan.report_path}{RESET}")
    print(f"  Summary:    {plan.summary}")

    print(f"\n{BLUE}{BOLD}Findings{RESET}")
    if not plan.findings:
        print(f"  {DIM}No issues found.{RESET}")
    for idx, finding in enumerate(plan.findings, start=1):
        print(
            f"  {idx}. {WHITE}{finding.title}{RESET} "
            f"{DIM}[impact={finding.impact_score} "
            f"risk={finding.risk_score} "
            f"confidence={finding.confidence_score}]{RESET}"
        )
        print(f"     {finding.summary}")

    print(f"\n{BLUE}{BOLD}Actions{RESET}")
    if not plan.actions:
        print(f"  {DIM}No actions proposed.{RESET}")
    for idx, action in enumerate(plan.actions, start=1):
        risk_label = "high-risk" if action.high_risk else "approved flow"
        print(
            f"  {idx}. {WHITE}{action.title}{RESET} "
            f"{DIM}[{action.action_type} | {risk_label}]{RESET}"
        )
        print(f"     ID: {action.action_id}")
        print(f"     {action.summary}")
        if action.confirmation_code:
            print(f"     Confirmation code: {YELLOW}{action.confirmation_code}{RESET}")


def _print_storeops_diffs(diffs: list[StructuredDiff]) -> None:
    print(f"\n{BLUE}{BOLD}Diff Preview{RESET}")
    if not diffs:
        print(f"  {DIM}No diffs generated.{RESET}")
        return
    for idx, diff in enumerate(diffs, start=1):
        print(f"  {idx}. {WHITE}{diff.target_type}{RESET} {diff.target_id}")
        print(f"     {diff.summary}")
        if diff.before:
            print(f"     Before: {DIM}{json.dumps(diff.before, ensure_ascii=False)}{RESET}")
        if diff.after:
            print(f"     After:  {json.dumps(diff.after, ensure_ascii=False)}")


def _print_apply_result(result: ApplyResult) -> None:
    print(f"\n{BLUE}{BOLD}Apply Result{RESET}")
    print(f"  Plan ID: {WHITE}{result.plan_id}{RESET}")
    print(f"  Mode:    {DIM}{'dry_run' if result.dry_run else 'execute'}{RESET}")
    print(f"  {result.message}")
    if result.executed_actions:
        print(f"  Executed: {', '.join(result.executed_actions)}")
    if result.blocked_actions:
        print(f"  Blocked:  {', '.join(result.blocked_actions)}")
    for decision in result.decisions:
        print(f"  - {decision.action_id}: {decision.decision} {decision.reason}")
    if result.diffs:
        _print_storeops_diffs(result.diffs)


def _prompt_storeops_approvals(plan: ActionPlan) -> tuple[set[str], dict[str, str]]:
    approved: set[str] = set()
    confirmation_codes: dict[str, str] = {}
    for action in plan.actions:
        print(f"\n  {WHITE}{action.title}{RESET}")
        print(f"    {DIM}{action.summary}{RESET}")
        try:
            answer = input(f"  {YELLOW}Approve this action? (y)es / (n)o: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "n"
        if answer not in ("y", "yes", "s", "si"):
            continue
        approved.add(action.action_id)
        if action.confirmation_code:
            try:
                typed = input(
                    f"  {YELLOW}Type confirmation code {action.confirmation_code}: {RESET}"
                ).strip()
            except (KeyboardInterrupt, EOFError):
                typed = ""
            confirmation_codes[action.action_id] = typed
    return approved, confirmation_codes


def handle_storeops_command(user_input: str, *, thread_id: str) -> bool:
    cmd = user_input.split()[0].lower()
    args = user_input[len(cmd) :].strip()

    try:
        if cmd == "/audit":
            spinner = Spinner("Running StoreOps audit")
            spinner.start()
            result = run_audit(
                AuditRequest(
                    store_id=TIENDANUBE_STORE_ID,
                    dry_run=True,
                    language=store_language(),
                    thread_id=thread_id,
                )
            )
            spinner.stop()
            _print_storeops_plan(result.plan)
            print(f"\n  Report saved to {DIM}{result.report_path}{RESET}")
            return True

        if cmd == "/plan":
            plan = load_latest_plan()
            _print_storeops_plan(plan)
            return True

        if cmd == "/dry-run":
            spinner = Spinner("Previewing StoreOps plan")
            spinner.start()
            result = preview_saved_plan(args or None)
            spinner.stop()
            plan = load_latest_plan() if not args or args == "latest" else load_plan(args)
            _print_storeops_plan(plan)
            _print_storeops_diffs(result.diffs)
            return True

        if cmd == "/apply":
            if not args:
                print(f"  {DIM}Usage: /apply <plan_id>{RESET}")
                return True
            plan = load_latest_plan() if args == "latest" else load_plan(args)
            _print_storeops_plan(plan)
            approved, confirmation_codes = _prompt_storeops_approvals(plan)
            spinner = Spinner("Applying StoreOps plan")
            spinner.start()
            result = apply_saved_plan(
                plan.plan_id,
                dry_run=False,
                confirmation_codes=confirmation_codes,
                approved_action_ids=approved,
            )
            spinner.stop()
            _print_apply_result(result)
            return True
    except FileNotFoundError as exc:
        print(f"  {RED}{exc}{RESET}")
        return True
    except Exception as exc:
        print(f"  {RED}StoreOps error: {exc}{RESET}")
        return True

    return False


def stream_response(agent, input_value, config, *, debug=False):
    """Stream agent response chunks to stdout.

    Returns True if the stream completed normally, False if interrupted.
    The caller should check for pending HITL interrupts after this returns.
    """
    spinner = Spinner("Thinking")
    spinner.start()
    first_text = True
    pending_tool_calls: dict[int, dict] = {}

    try:
        for chunk, metadata in agent.stream(
            input_value,
            config=config,
            stream_mode="messages",
        ):
            if isinstance(chunk, ToolMessage):
                if debug:
                    spinner.stop()
                    content = str(chunk.content)
                    if len(content) > 500:
                        content = content[:500] + f"... ({len(content)} chars)"
                    print(f"  {GREEN}← {chunk.name}{RESET}")
                    print(f"    {DIM}{content}{RESET}")
                continue

            if not isinstance(chunk, AIMessageChunk):
                continue

            if isinstance(chunk.content, list):
                for block in chunk.content:
                    if not isinstance(block, dict):
                        continue

                    if block.get("type") == "function_call":
                        idx = block.get("index", 0)
                        if "name" in block and block["name"]:
                            pending_tool_calls[idx] = {
                                "name": block["name"],
                                "args": block.get("arguments", ""),
                            }
                            spinner.update(f"Calling {block['name']}")
                            if debug:
                                spinner.stop()
                                print(f"  {CYAN}→ {block['name']}{RESET}", end="", flush=True)
                                spinner.start()
                        elif "arguments" in block and idx in pending_tool_calls:
                            pending_tool_calls[idx]["args"] += block["arguments"]

                    elif block.get("type") == "text" and block.get("text"):
                        if first_text:
                            spinner.stop()
                            print()
                            first_text = False
                        print(block["text"], end="", flush=True)

            elif isinstance(chunk.content, str) and chunk.content:
                if first_text:
                    spinner.stop()
                    print()
                    first_text = False
                print(chunk.content, end="", flush=True)

        spinner.stop()

        if debug and pending_tool_calls:
            for _idx, call in pending_tool_calls.items():
                formatted = format_json_debug(call["args"])
                print(f"  {YELLOW}⤷ {call['name']}({formatted}){RESET}")

        return True

    except KeyboardInterrupt:
        spinner.stop()
        print(f"\n  {DIM}[Interrupted]{RESET}")
        return False
    except Exception as e:
        spinner.stop()
        if debug:
            import traceback

            print(f"\n  {RED}Error: {e}{RESET}")
            traceback.print_exc()
        else:
            print(f"\n  {RED}Error: {e}{RESET}")
        return False


def _prompt_decisions(action_requests):
    """Prompt the user for approve/reject on each action request."""
    decisions = []
    for action in action_requests:
        tool_name = action.get("name", "unknown")
        tool_args = action.get("args", {})

        print(f"\n  {YELLOW}Destructive action requested:{RESET}")
        print(f"  {WHITE}{tool_name}{RESET}")
        if tool_args:
            args_str = json.dumps(tool_args, ensure_ascii=False, indent=2)
            for line in args_str.split("\n"):
                print(f"    {DIM}{line}{RESET}")

        try:
            answer = input(f"  {YELLOW}Approve? (y)es / (n)o: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "n"

        if answer in ("y", "yes", "s", "si"):
            decisions.append({"type": "approve"})
        else:
            decisions.append(
                {
                    "type": "reject",
                    "message": "User rejected this action.",
                }
            )
    return decisions


def handle_interrupts(agent, config, *, debug=False):
    """Check for pending HITL interrupts and prompt the user for decisions.

    The HITL middleware sends an HITLRequest with ``action_requests`` (list of
    ActionRequest dicts, each with ``name``, ``args``, and optional
    ``description``).  We display each action and collect approve/reject
    decisions, then resume the graph with ``Command(resume=...)``.

    When multiple interrupts are pending (e.g. from different sub-agents),
    we key the resume dict by interrupt ID — required by LangGraph when
    there are >1 pending interrupts.

    Returns True if an interrupt was handled, False if there were none.
    """
    state = agent.get_state(config)
    if not state.interrupts:
        return False

    # Collect decisions keyed by interrupt ID (official deepagents pattern).
    # Each interrupt maps to {"decisions": [...]}.
    hitl_response = {}
    for intr in state.interrupts:
        request_data = intr.value
        if not isinstance(request_data, dict):
            continue

        action_requests = request_data.get("action_requests", [])
        if not action_requests:
            continue

        decisions = _prompt_decisions(action_requests)
        if decisions:
            hitl_response[intr.id] = {"decisions": decisions}

    if not hitl_response:
        return False

    resume_value = Command(resume=hitl_response)
    stream_response(agent, resume_value, config, debug=debug)

    # Check for further interrupts (in case of chained destructive calls)
    handle_interrupts(agent, config, debug=debug)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Nube Agent - Tiendanube Store Manager")
    parser.add_argument("--debug", action="store_true", help="Start with debug mode on")
    args = parser.parse_args()
    debug = args.debug

    validate()

    # Fetch store info for banner before building agent
    spinner = Spinner("Connecting to store")
    spinner.start()
    store_name, store_domain, store_currency = fetch_store_summary()
    agent = build_agent()
    spinner.stop()

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print_banner(store_name, store_domain, store_currency)
    if debug:
        print(f"  {YELLOW}debug mode on{RESET}\n")

    prompt_str = f"{BLUE}❯{RESET} "

    while True:
        try:
            user_input = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Bye!{RESET}")
            break

        if not user_input:
            continue

        if user_input.startswith("/") and handle_storeops_command(user_input, thread_id=thread_id):
            print()
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            result = handle_slash(user_input)
            if result is None:
                continue
            if result == "__EXIT__":
                print(f"{DIM}Bye!{RESET}")
                break
            if result == "__TOGGLE_DEBUG__":
                debug = not debug
                state = "on" if debug else "off"
                print(f"  {YELLOW}debug mode {state}{RESET}\n")
                continue
            # Replace input with the expanded prompt
            user_input = result

        # Handle plain exit/quit
        if user_input.lower() in ("exit", "quit"):
            print(f"{DIM}Bye!{RESET}")
            break

        input_value = {"messages": [{"role": "user", "content": user_input}]}
        completed = stream_response(agent, input_value, config, debug=debug)

        if completed:
            handle_interrupts(agent, config, debug=debug)

        print()


if __name__ == "__main__":
    main()
