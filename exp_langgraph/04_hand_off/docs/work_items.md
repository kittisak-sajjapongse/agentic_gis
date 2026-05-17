# POC Work Items (Ordered, Testable)

This backlog is ordered so each item can be completed and verified before moving to the next.
Scope is proof-of-concept only.

## Compact Status View

| Item | Status | Owner | Updated |
|---|---|---|---|
| [BACKEND-001](#BACKEND-001) | DONE | Codex | 2026-05-15 |
| [BACKEND-002](#BACKEND-002) | DONE | Codex | 2026-05-15 |
| [STORAGE-001](#STORAGE-001) | DONE | Codex | 2026-05-15 |
| [BACKEND-003](#BACKEND-003) | DONE | Codex | 2026-05-16 |
| [BACKEND-004](#BACKEND-004) | DONE | Codex | 2026-05-16 |
| [BACKEND-005](#BACKEND-005) | DONE | Codex | 2026-05-16 |
| [AGENT-001](#AGENT-001) | DONE | Codex | 2026-05-16 |
| [BACKEND-006](#BACKEND-006) | DONE | Codex | 2026-05-16 |
| [AGENT-002](#AGENT-002) | DONE | Codex | 2026-05-16 |
| [UI-001](#UI-001) | DONE | Codex | 2026-05-16 |
| [UI-002](#UI-002) | TODO | Unassigned | - |
| [UI-003](#UI-003) | TODO | Unassigned | - |
| [UI-004](#UI-004) | TODO | Unassigned | - |
| [BACKEND-007](#BACKEND-007) | TODO | Unassigned | - |
| [BACKEND-008](#BACKEND-008) | TODO | Unassigned | - |
| [QA-001](#QA-001) | TODO | Unassigned | - |

<a id="BACKEND-001"></a>

## BACKEND-001 [DONE] - Create HTTP API skeleton and health endpoint
**Component:** BACKEND

**Goal**
- Introduce a minimal web API app process for the project without changing agent logic.

**Deliverables**
- API app bootstrap entrypoint.
- `GET /api/health` returns service status and timestamp.

**Acceptance Criteria**
- API starts locally.
- `GET /api/health` returns `200` with JSON body containing `status: "ok"`.

**Verification**
1. Start backend API process.
2. Run `curl -s http://localhost:<port>/api/health`.
3. Confirm JSON response includes `status` and current timestamp.

---

<a id="BACKEND-002"></a>

## BACKEND-002 [DONE] - Add session creation and fetch APIs
**Component:** BACKEND

**Goal**
- Add session lifecycle primitives required by UI.

**Deliverables**
- `POST /api/sessions` creates session.
- `GET /api/sessions/:sessionId` returns session metadata.

**Acceptance Criteria**
- Creating a session returns unique `sessionId`.
- Fetching the new session returns `active` status.

**Verification**
1. `POST /api/sessions`.
2. Save returned `sessionId`.
3. `GET /api/sessions/<sessionId>`.
4. Confirm response contains same ID and valid status.

---

<a id="STORAGE-001"></a>

## STORAGE-001 [DONE] - Implement local artifact provider abstraction
**Component:** STORAGE

**Goal**
- Introduce storage abstraction for artifacts with local filesystem implementation.

**Deliverables**
- `ArtifactProvider` interface.
- `LocalArtifactProvider` implementation for read/write/metadata.

**Acceptance Criteria**
- Provider can register an artifact path and resolve read metadata.
- Provider can stream artifact content bytes from local file.

**Verification**
1. Register a known file under `data/` as an artifact.
2. Call provider read method.
3. Confirm returned content/metadata match source file.

---

<a id="BACKEND-003"></a>

## BACKEND-003 [DONE] - Expose artifact content API
**Component:** BACKEND

**Goal**
- Serve GIS artifact data through API (UI-safe access path).

**Deliverables**
- `GET /api/artifacts/:artifactId/content` endpoint.
- Uses `ArtifactProvider` only (no direct ad-hoc file path reads in handler).

**Acceptance Criteria**
- Endpoint returns `200` and correct content type for known artifact.
- Unknown artifact returns `404`.

**Verification**
1. Request known artifact content endpoint.
2. Confirm response body is non-empty and content type is expected.
3. Request unknown artifact and confirm `404`.

---

<a id="BACKEND-004"></a>

## BACKEND-004 [DONE] - Add layer domain contract and registry service
**Component:** BACKEND

**Goal**
- Add typed layer model and session-scoped layer registry.

**Deliverables**
- Layer descriptor model (`id`, `kind`, `source`, `style`, `origin`, etc.).
- Registry service storing input/output layers by session.
- `GET /api/sessions/:sessionId/layers`.
- `GET /api/layers/:layerId`.

**Acceptance Criteria**
- Session returns deterministic list of layers.
- Layer fetch by ID returns exact stored descriptor.

**Verification**
1. Seed one input layer in a test session.
2. Call list layers endpoint and verify item appears.
3. Fetch layer by ID and compare fields.

---

<a id="BACKEND-005"></a>

## BACKEND-005 [DONE] - Add layer patch endpoint for UI state updates
**Component:** BACKEND

**Goal**
- Let UI persist visibility/opacity/style override changes.

**Deliverables**
- `PATCH /api/layers/:layerId` with allowed mutable fields.

**Acceptance Criteria**
- Patch updates only permitted fields.
- Validation rejects invalid payloads with `400`.

**Verification**
1. Patch `visible=false` and `opacity=0.5` on existing layer.
2. Fetch layer and confirm values updated.
3. Send invalid opacity (e.g., `2.5`) and confirm `400`.

---

<a id="AGENT-001"></a>

## AGENT-001 [DONE] - Create run orchestration API to invoke existing graph
**Component:** AGENT

**Goal**
- Bridge chat request to current LangGraph runtime.

**Deliverables**
- `POST /api/sessions/:sessionId/chat` starts run and returns `runId`.
- Run service invokes existing graph path (no graph routing logic moved to agents).

**Acceptance Criteria**
- Endpoint returns run ID immediately.
- Run state transitions to `running` then `completed` or `failed`.

**Verification**
1. Submit a simple prompt through chat endpoint.
2. Poll run status endpoint.
3. Confirm run reaches terminal state.

---

<a id="BACKEND-006"></a>

## BACKEND-006 [DONE] - Add SSE stream endpoint for run events
**Component:** BACKEND

**Goal**
- Stream incremental events for chat and tool progress.

**Deliverables**
- `GET /api/runs/:runId/stream` SSE endpoint.
- Emits at least: `message`, `tool_start`, `tool_end`, `done`, `error`.

**Acceptance Criteria**
- SSE stream remains open during run.
- Events are ordered and include `runId`, `sessionId`, `timestamp`.

**Verification**
1. Start a run.
2. Connect using `curl -N` to SSE endpoint.
3. Confirm events stream until `done`/`error`.

---

<a id="AGENT-002"></a>

## AGENT-002 [DONE] - Emit `layer_created` events and persist output layers
**Component:** AGENT

**Goal**
- Make agent outputs discoverable by map UI automatically.

**Deliverables**
- On output artifact creation, register `LayerDescriptor` in layer registry.
- Emit SSE `layer_created` with `layerId`.

**Acceptance Criteria**
- Runs producing GIS output emit `layer_created` at least once.
- New layer appears in `GET /api/sessions/:sessionId/layers`.

**Verification**
1. Trigger prompt that generates output layer.
2. Observe `layer_created` on SSE stream.
3. Fetch session layers and confirm new output layer exists.

---

<a id="UI-001"></a>

## UI-001 [DONE] - Bootstrap React + TypeScript app shell
**Component:** UI

**Goal**
- Create standalone UI app under `ui/` and render baseline layout.

**Deliverables**
- 3-pane layout: Layer Panel, Map Pane, Chat Pane.
- Health indicator calling `/api/health`.

**Acceptance Criteria**
- UI starts and renders all panes.
- Health status shows backend connectivity.

**Verification**
1. Start backend and UI dev servers.
2. Open browser.
3. Confirm layout and successful health check state.

---

<a id="UI-002"></a>

## UI-002 [TODO] - Integrate MapLibre with session layer listing
**Component:** UI

**Goal**
- Render input/output layers from backend in map + panel.

**Deliverables**
- Session bootstrap flow.
- Fetch and render layers from `GET /api/sessions/:sessionId/layers`.
- Layer visibility toggles wired to `PATCH /api/layers/:layerId`.

**Acceptance Criteria**
- Existing layers draw on map.
- Visibility toggle updates both map and backend state.

**Verification**
1. Load UI with seeded layers.
2. Confirm layers visible on map.
3. Toggle one layer off/on and verify persisted state via API.

---

<a id="UI-003"></a>

## UI-003 [TODO] - Integrate assistant-ui chat + run streaming
**Component:** UI

**Goal**
- Enable chat-driven runs with live streaming updates.

**Deliverables**
- Chat submit to `POST /api/sessions/:sessionId/chat`.
- SSE subscription to `/api/runs/:runId/stream`.
- Render streamed messages and tool statuses.

**Acceptance Criteria**
- Prompt submission starts run and displays streaming output.
- End-of-run status shown in chat.

**Verification**
1. Send prompt from chat panel.
2. Confirm streamed events appear in UI.
3. Confirm run completion status is visible.

---

<a id="UI-004"></a>

## UI-004 [TODO] - Auto-add agent output layers from SSE events
**Component:** UI

**Goal**
- Automatically add map layers when agent creates them.

**Deliverables**
- Handle `layer_created` SSE event.
- Fetch descriptor using `GET /api/layers/:layerId`.
- Insert new layer into output section and map rendering.

**Acceptance Criteria**
- New output layer appears in panel/map without page reload.
- User can toggle and inspect newly added layer.

**Verification**
1. Execute prompt that generates layer output.
2. Confirm `layer_created` causes immediate map update.
3. Toggle new layer and confirm behavior.

---

<a id="BACKEND-007"></a>

## BACKEND-007 [TODO] - Add POC catalog import endpoints for local GIS files
**Component:** BACKEND

**Goal**
- Provide explicit API to discover/import local datasets into a session.

**Deliverables**
- `GET /api/catalog` to list available local datasets.
- `POST /api/sessions/:sessionId/layers/import` to add selected dataset as input layer.

**Acceptance Criteria**
- Catalog endpoint lists datasets with stable IDs and metadata.
- Import endpoint creates layer in target session.

**Verification**
1. Call catalog endpoint and capture one `catalogItemId`.
2. Import it into session.
3. Verify imported layer appears in session layer list and on UI map.

---

<a id="BACKEND-008"></a>

## BACKEND-008 [TODO] - Add minimal persistence for sessions/runs/layers (POC-safe)
**Component:** BACKEND

**Goal**
- Preserve state across backend restarts during development.

**Deliverables**
- Simple persistence layer (e.g., lightweight DB or file-backed store).
- Persist sessions, runs, layers, and artifact metadata.

**Acceptance Criteria**
- Restarting backend retains previously created session and layers.
- UI can reconnect and restore state.

**Verification**
1. Create session and run that generates output layer.
2. Restart backend.
3. Fetch session/layers again and confirm data remains.

---

<a id="QA-001"></a>

## QA-001 [TODO] - End-to-end POC validation checklist
**Component:** QA

**Goal**
- Verify complete POC behavior from UI through agent output on map.

**Deliverables**
- Repeatable validation script/checklist covering:
  - session creation
  - chat run
  - SSE stream
  - layer creation
  - map rendering
  - layer toggle persistence

**Acceptance Criteria**
- Checklist passes on clean startup with documented commands.
- Known limitations and non-goals are documented.

**Verification**
1. Execute full checklist in order.
2. Capture pass/fail results.
3. Record defects and follow-up work items.
