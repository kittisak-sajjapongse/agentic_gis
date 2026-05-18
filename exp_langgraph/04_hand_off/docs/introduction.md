# Project Introduction

## What We Are Building

We are adding a web-based GIS + AI workspace to this project so users can:
- Chat with agents to request geospatial analysis
- View both input GIS layers and agent-produced output layers on an interactive map
- Iterate quickly by asking follow-up questions in the same session

The initial target is a **proof-of-concept (POC)** that is easy to understand and extend.

---

## Why This Matters

Today, analysis logic exists in the backend/agent runtime, but there is no dedicated web UI that unifies:
- map-based visualization,
- layer lifecycle management, and
- conversational interaction with agents.

This project closes that gap with a practical, testable architecture that supports incremental development.

---

## Who This Is For

### Project Managers
- Clear delivery plan with ordered work items and test checkpoints
- Reduced risk through incremental integration
- Straightforward path from POC to production

### Engineers
- Clean architecture boundaries aligned with `AGENTS.md`
- Typed API contracts for stable integration
- Separation of concerns across UI, backend API, and agent runtime

### Analysts
- Ability to inspect source layers, generated outputs, and run progression
- Reproducible analysis sessions and visible processing status

### Coding AI / Agent Contributors
- Explicit contracts, endpoint patterns, and event schema
- Layered responsibilities to avoid architectural drift
- Small, testable tasks for safe implementation steps

---

## Current Scope (POC)

The POC focuses on the minimum complete workflow:
1. Start a session
2. Load available GIS layers
3. Send chat prompt to agent runtime
4. Stream run/tool/message events to UI
5. Display newly generated output layers automatically
6. Toggle/inspect layers on the map

Out of scope for POC:
- full enterprise auth model
- large-scale multi-tenant hardening
- advanced geospatial tile optimization pipeline

---

## How We Are Building It

## 1) Architecture Overview

The solution has three connected parts:
1. **UI (React + TypeScript)**
- Map rendering (MapLibre)
- Chat panel (`assistant-ui`)
- Layer panel for visibility and output tracking

2. **Backend API (Python in this repo)**
- REST endpoints for sessions, layers, runs
- SSE endpoint for streaming run events
- Artifact-serving endpoints for GIS data

3. **Agent Runtime (existing LangGraph flow)**
- Uses current `graphs/`, `agents/`, `tools/`, `domain/`, `runtime/`
- Produces chat responses and GIS output artifacts/layers

Storage in POC is local filesystem, abstracted through a provider to allow future S3-like migration.

## 2) Communication Channels

- UI -> Backend: HTTP REST JSON
- Backend -> UI: SSE (`text/event-stream`) for real-time progress
- Backend -> Agent runtime: in-process Python invocation
- Agent runtime <-> Storage: provider abstraction
  - POC: local file I/O
  - Production: S3-compatible object storage APIs

## 3) API Design Direction

Core endpoint families:
- Session APIs
- Run/chat APIs
- Layer APIs
- Artifact content APIs
- SSE stream for run events (`message`, `tool_start`, `tool_end`, `layer_created`, `done`, `error`)

Immediate priority (blocking):
- Human-in-the-loop clarification handling (HITL) so interrupt questions are
  resumed as expected workflow, not surfaced as generic SSE errors.
- Output render compatibility so generated GeoParquet layers are converted into
  map-consumable sources and visibly rendered in the UI.

Design principles:
- typed contracts for interoperability
- backend-mediated artifact access (UI never reads local disk directly)
- stable payloads so storage backend can change without UI rewrite

Show-layer strategy:
- Implement `show_layer(...)` in backend service layer as the source-of-truth
  capability for agent/user requests to show known layers.
- In production, expose `POST /api/sessions/:sessionId/layers/show` backed by
  that service method for a clean explicit command contract.
- Keep catalog APIs for manual discovery/import flows.

---

## Technology Choices and Rationale

### UI Stack
- **React + TypeScript**: requested preference, good component and typing ecosystem
- **MapLibre GL JS**: open mapping stack, strong for baseline GIS layer rendering
- **assistant-ui**: reusable chat UI primitives to avoid building chat UX from scratch

### Why Not `deck.gl` First
- `deck.gl` is valuable for very large/advanced visualization.
- For POC speed and clarity, MapLibre alone is enough.
- `deck.gl` can be added later when performance/visual requirements justify it.

### Backend and Agent Reuse
- Reuse existing LangGraph-based backend logic and OOP boundaries.
- Add API and contracts around current runtime rather than refactoring core agent behavior.

---

## Repository Context and Constraints

This repository already organizes logic by responsibility:
- `domain/` contracts and state
- `agents/` LLM behavior
- `tools/` integrations and adapters
- `graphs/` topology and routing
- `runtime/` config and dependency wiring

New UI is expected as a separate subdirectory (`ui/`) to avoid mixing frontend code into backend runtime modules.

---

## Delivery Strategy

Implementation is planned as **ordered, testable work items** so each step can be verified before moving on.

Reference backlog:
- [work_items.md](/Users/kittisak/data/work/agentic_gis/exp_langgraph/04_hand_off/docs/work_items.md)

This allows:
- progressive understanding of codebase and integration points
- easier debugging and rollback scope
- clearer progress tracking for technical and non-technical stakeholders
- explicit handling of blocking features first (current: HITL resume flow)

---

## POC to Production Path

The architecture is intentionally designed for minimal-change migration.

### POC
- Local artifact storage
- API-driven map + chat workflow
- Session/run/layer contracts validated end-to-end

### Production Evolution
- Keep API and UI contracts stable
- Swap storage provider to S3-compatible implementation
- Add auth, persistence hardening, observability, lifecycle policies

Because the UI consumes stable layer/artifact URLs and metadata contracts, storage changes can remain backend-only.

---

## Risks and Mitigations

1. Contract drift between UI and backend
- Mitigation: define typed models early and validate payloads in tests

2. Event ordering/reliability in streaming flows
- Mitigation: run-state model + explicit terminal events + reconnect behavior

3. Large GIS artifact performance
- Mitigation: start with POC-level datasets; introduce tiling/caching/CDN in production phase

4. Architectural boundary erosion
- Mitigation: enforce `AGENTS.md` layering rules for all new code

---

## Success Criteria for the POC

The POC is successful when a new user can:
1. start the app,
2. open a session,
3. ask an agent to perform GIS analysis,
4. observe real-time run progress,
5. see new output layers added to the map,
6. control and inspect those layers in the UI.

---

## Related Documents

- Architecture details: [architecture.md](/Users/kittisak/data/work/agentic_gis/exp_langgraph/04_hand_off/docs/architecture.md)
- Ordered implementation backlog: [work_items.md](/Users/kittisak/data/work/agentic_gis/exp_langgraph/04_hand_off/docs/work_items.md)
- Contributor boundary rules: `AGENTS.md`
