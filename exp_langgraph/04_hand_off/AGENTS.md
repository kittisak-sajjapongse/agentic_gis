# AGENTS.md

Guidelines for contributors/agents working in `exp_langgraph/04_hand_off`.

## Purpose

Preserve the current OOP boundaries while evolving the GIS hand-off workflow.

## Design Rules

1. `domain/` is the source of truth for shared contracts and business data.
- Put shared state/data models in `domain/state_models.py`.
- Put static domain datasets in `domain/` (e.g., GIS catalog data).

2. `agents/` contains LLM behavior only.
- Prompt, tool-binding, and response parsing belong here.
- Do not add graph edge/routing logic in agent classes.

3. `tools/` owns integrations and tool execution adapters.
- External integration setup (MCP, API clients, etc.) belongs in providers.
- Reuse `ToolExecutorNode`; do not duplicate ad-hoc tool node wrappers.

4. `graphs/` owns topology and routing.
- Node functions, conditional routing, and compile steps belong here.
- Avoid embedding large prompt/business parsing logic in graph modules.

5. `runtime/` owns config and dependency construction.
- Environment parsing belongs in `runtime/settings.py`.
- Shared object factories belong in `runtime/container.py`.

6. Entry points stay thin.
- `main.py` and `main_cli.py` should orchestrate session I/O only.

## Coding Conventions

- Prefer dependency injection over module-level mutable globals.
- Prefer typed models/contracts over ad-hoc dicts for cross-layer state.
- Keep compatibility shims temporary and remove them once imports are migrated.
- Keep function/module names aligned with responsibility (`*_graph`, `*_agent`, `*_tools`).

## Change Checklist

Before submitting changes:

0. Design Conformance
- Cross-check implementation against:
  - `docs/introduction.md`
  - `docs/architecture.md`
  - `docs/work_items.md`
  - `docs/coding_conventions.md`
- Confirm the change follows the intended scope, API contracts, and current work-item priority/EPIC ordering.
- If implementation intentionally deviates from these docs, document the reason and update the relevant doc(s) in the same change.

1. Architecture
- Confirm code is placed in the correct layer (`domain/agents/tools/graphs/runtime`).
- Confirm no new circular imports are introduced.

2. Quality
- Run compile check:
  - `python -m py_compile $(rg --files -g '*.py')`
- If behavior changed, run the relevant runtime path (CLI).

3. Contract Safety
- If state contracts changed, update `domain/state_models.py` first.
- Validate all affected agents/graphs still compile and use updated fields.

4. Docs
- Update `README.md` when structure or extension workflow changes.

## Anti-Patterns to Avoid

- Reintroducing old root-level mixed modules (state + agents + graph + tools together).
- Adding hidden singletons/globals for MCP clients or tools in graph modules.
- Duplicating tool execution logic instead of reusing `ToolExecutorNode`.
- Putting domain entities inside graph modules.
