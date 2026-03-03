# StoreOps Copilot Demo

This branch showcases a StoreOps Copilot prototype built on top of the `nube-agent` CLI for Tiendanube / Nuvemshop stores.

It focuses on a concrete engineering problem: how should an AI agent help improve store operations without turning execution into an opaque or unsafe automation layer?

The prototype emphasizes structured audits, reviewable plans, dry-run safety, and explicit approval before risky actions.

## Overview

The StoreOps layer extends the original agent with an operational workflow that inspects store state, produces structured actions, previews changes safely, and requires approval before risky execution.

Core workflow:

`audit -> plan -> dry-run -> approval -> execution`

## Key Capabilities

- Runs store audits across catalog, marketing, and order workflows
- Produces ranked action plans with explicit impact and risk signals
- Supports dry-run previews before execution
- Blocks mutating HTTP calls during dry-run mode with a request-boundary mutation firewall
- Requires explicit approval for destructive or high-risk actions
- Persists reports and StoreOps memory in a local filesystem-backed workspace
- Includes automated tests and local evals for core safety behavior

## Architecture Overview

```text
User / CLI
  |
  +-- /audit ---------> StoreOps audit runner
  |                      |
  |                      +-- collect API snapshot
  |                      +-- run deterministic checks
  |                      +-- rank findings and actions
  |                      +-- save report + plan memory
  |
  +-- /plan ----------> load latest saved plan
  +-- /dry-run -------> preview diffs only
  +-- /apply <plan> --> approval flow + guarded execution
  |
  +-- natural language -> main agent + domain subagents
```

## Safety Model

The prototype uses layered safeguards rather than relying on a single confirmation step.

- Destructive actions remain gated through human-in-the-loop interruptions
- High-risk actions require explicit approval
- High-risk bulk actions require a typed confirmation code
- Dry-run mode is enforced at the HTTP boundary, so mutating methods cannot be sent accidentally
- Policy checks run before execution
- Local evals check dry-run purity and policy compliance

## Key Commands

```bash
nube-agent
```

Inside the CLI:

- `/audit` runs a StoreOps audit and saves a plan
- `/plan` shows the latest saved plan
- `/dry-run` previews the planned diffs without mutation
- `/apply <plan_id>` executes approved actions
- `/debug` toggles tool-call visibility

## Quickstart

Install:

```bash
pip install -e ".[dev]"
```

Configure:

```bash
cp .env.example .env
```

Required environment variables:

- `OPENAI_API_KEY`
- `TIENDANUBE_ACCESS_TOKEN`
- `TIENDANUBE_STORE_ID`

Run:

```bash
nube-agent
```

## 3-Minute Demo Script

1. Launch the CLI and explain that the project starts from a working Tiendanube agent rather than a greenfield toy app.
2. Run `/audit` and describe the flow: snapshot collection, deterministic checks, ranked findings, and saved action plan.
3. Run `/plan` to show that the audit output is persisted and reviewable.
4. Run `/dry-run` to show structured diffs and explain that dry-run is protected by the mutation firewall at the request boundary.
5. If useful, show `/apply <plan_id>` and explain that risky actions require explicit approval and confirmation codes.
6. Close with the test and eval story: this is not just a UI demo, it has repeatable safety checks.

## Validation

Run the full test suite:

```bash
pytest -q
```

Run lint:

```bash
ruff check src tests
```

Run the local StoreOps evals:

```bash
python -m nube_agent.storeops.evals
```

## Repository Focus

This demo branch is intentionally curated for readability.

- It keeps the full StoreOps prototype codepath
- It removes internal planning noise and scratch artifacts
- It is meant to be read as an engineering prototype, not as an AI-generated dump
