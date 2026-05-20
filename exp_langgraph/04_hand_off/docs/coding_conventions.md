# Coding Conventions

This document defines practical coding conventions for this codebase.

## 1) Layered Architecture Placement
- Put shared contracts and canonical models in `domain/`.
- Put LLM prompt/response behavior in `agents/`.
- Put graph routing/topology in `graphs/`.
- Put integrations and execution adapters in `tools/`.
- Put config/composition in `runtime/`.
- Keep API entrypoints thin (`api/app.py`, `main_api.py`).

## 2) Type-Safe Contracts First
- Prefer typed models (Pydantic/dataclasses) for cross-layer data.
- Update shared contracts in `domain/state_models.py` before dependent logic.
- Avoid passing unstructured dicts across module boundaries when a model exists.

## 3) Dict Access: `get()` vs `[]`
- Use `dict.get("key")` for optional/external data:
  - API payloads from tools/LLMs
  - catalog metadata that may be incomplete
  - backward-compatible fields
- Use `dict["key"]` only when key presence is guaranteed by contract and missing key should fail fast.
- Reason: `get()` prevents avoidable `KeyError` crashes at system boundaries.

## 4) Normalization and Guardrails
- Prompt instructions are not enough for correctness.
- Add code-level normalization for control-flow fields and invariants.
- Example pattern:
  - normalize/validate parsed LLM JSON
  - coerce unknown/None route keys to safe defaults
  - emit actionable errors for invalid states

## 5) Error Handling and Observability
- Prefer actionable error messages over generic failures.
- Log stack traces on backend failures with context (run id, session id, component).
- Keep SSE/API payloads stable and explicit.

## 6) API Conventions
- Use REST paths with `{param}` style in implementation.
- Return JSON-serializable models via `model_dump()`.
- Validate request inputs early and return clear 4xx errors.

## 7) State and Persistence
- In-memory storage is acceptable for POC only.
- Mark production gaps with explicit `TODO(PROD)` comments.
- Avoid hidden globals; inject dependencies where possible.

## 8) UI Synchronization
- Do not rely on a single real-time event for correctness.
- Add convergence paths (periodic refresh/final reload) for race tolerance.
- Handle terminal catch-up states for late subscribers.

## 9) Testing and Verification
- Add focused regression tests for each bug fixed.
- Use `pytest` as the default test runner for this repository.
- Use file naming to indicate test intent:
  - `test_workflow_*.py` for end-to-end or user workflow tests
  - `test_<component>_<behavior>.py` for focused unit/regression checks
- If a code change impacts user workflow, add or update at least one
  `test_workflow_*.py` test that exercises the changed flow.
- Run checks after edits:
  - `python3 -m py_compile $(rg --files -g '*.py')`
  - `python3 -m pytest -q`

## 10) Commenting Style
- Add comments for non-obvious decisions and invariants.
- Avoid comments that restate trivial syntax.
- Prefer concise comments that explain *why*, not just *what*.
