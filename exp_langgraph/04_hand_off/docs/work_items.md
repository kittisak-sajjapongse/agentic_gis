# POC Work Items (Ordered, Testable)

This backlog is ordered so each item can be completed and verified before moving to the next.
Scope is proof-of-concept only.

## Compact Status View

| Item | EPIC | Status | Owner | Updated |
|---|---|---|---|---|
| [BACKEND-001](#BACKEND-001) | - | DONE | Codex | 2026-05-15 |
| [BACKEND-002](#BACKEND-002) | - | DONE | Codex | 2026-05-15 |
| [STORAGE-001](#STORAGE-001) | - | DONE | Codex | 2026-05-15 |
| [BACKEND-003](#BACKEND-003) | - | DONE | Codex | 2026-05-16 |
| [BACKEND-004](#BACKEND-004) | - | DONE | Codex | 2026-05-16 |
| [BACKEND-005](#BACKEND-005) | - | DONE | Codex | 2026-05-16 |
| [AGENT-001](#AGENT-001) | - | DONE | Codex | 2026-05-16 |
| [BACKEND-006](#BACKEND-006) | - | DONE | Codex | 2026-05-16 |
| [AGENT-002](#AGENT-002) | - | DONE | Codex | 2026-05-16 |
| [UI-001](#UI-001) | - | DONE | Codex | 2026-05-16 |
| [UI-002](#UI-002) | - | DONE | Codex | 2026-05-17 |
| [UI-003](#UI-003) | - | DONE | Codex | 2026-05-17 |
| [UI-004](#UI-004) | - | DONE | Codex | 2026-05-18 |
| [BACKEND-012](#BACKEND-012) | EPIC-HITL-001 | DONE | Codex | 2026-05-18 |
| [UI-007](#UI-007) | EPIC-HITL-001 | DONE | Codex | 2026-05-18 |
| [BACKEND-013](#BACKEND-013) | EPIC-HITL-001 | DONE | Codex | 2026-05-18 |
| [QA-003](#QA-003) | EPIC-HITL-001 | DONE | Codex | 2026-05-18 |
| [BACKEND-014](#BACKEND-014) | EPIC-RENDER-001 | DONE | Codex | 2026-05-18 |
| [BACKEND-015](#BACKEND-015) | EPIC-RENDER-001 | DONE | Codex | 2026-05-18 |
| [QA-004](#QA-004) | EPIC-RENDER-001 | DONE | Unassigned | - |
| [BACKEND-007](#BACKEND-007) | - | TODO | Unassigned | - |
| [BACKEND-008](#BACKEND-008) | - | TODO | Unassigned | - |
| [BACKEND-010](#BACKEND-010) | EPIC-LAYERSHOW-001 | TODO | Unassigned | - |
| [AGENT-003](#AGENT-003) | EPIC-LAYERSHOW-001 | TODO | Unassigned | - |
| [BACKEND-011](#BACKEND-011) | EPIC-LAYERSHOW-001 | TODO | Unassigned | - |
| [UI-006](#UI-006) | EPIC-LAYERSHOW-001 | TODO | Unassigned | - |
| [QA-002](#QA-002) | EPIC-LAYERSHOW-001 | TODO | Unassigned | - |
| [BACKEND-009](#BACKEND-009) | - | TODO | Unassigned | - |
| [UI-005](#UI-005) | - | TODO | Unassigned | - |
| [QA-001](#QA-001) | - | TODO | Unassigned | - |
| [BACKEND-016](#BACKEND-016) | - | TODO | Unassigned | - |

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

## UI-002 [DONE] - Integrate MapLibre with session layer listing
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

## UI-003 [DONE] - Integrate assistant-ui chat + run streaming
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

## UI-004 [DONE] - Auto-add agent output layers from SSE events
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

## EPIC-HITL-001 - Human-in-the-Loop Resume Flow
**Feature Goal**
- When agents request clarification, UI should present the question and allow user to continue the same run without treating it as a transport failure.

**Priority**
- Immediate / blocking for current POC usability.

---

<a id="BACKEND-012"></a>

## BACKEND-012 [DONE] - Emit HITL-specific SSE event and stop treating interrupt as generic error
**Component:** BACKEND
**EPIC:** `EPIC-HITL-001`

**Goal**
- Distinguish clarification interrupts from failures in the run event stream.

**Deliverables**
- Add SSE event type: `clarification_required`.
- Payload includes interrupt id + user-facing question.
- Keep run status as `interrupted` (not `failed`) for clarification paths.
- Avoid emitting generic `error` event for expected clarification interrupts.

**Acceptance Criteria**
- Clarification case emits `clarification_required`.
- UI no longer receives misleading terminal error for normal HITL requests.

**Verification**
1. Trigger prompt that causes clarification.
2. Confirm SSE includes `clarification_required` with `question`.
3. Confirm run status is `interrupted`, not `failed`.

---

<a id="UI-007"></a>

## UI-007 [DONE] - Add chat HITL state and clarification input flow
**Component:** UI
**EPIC:** `EPIC-HITL-001`

**Goal**
- Let user answer agent clarification questions directly in the chat panel.

**Deliverables**
- Render `clarification_required` event distinctly in chat UI.
- Preserve interrupt metadata (`runId`, `interruptId`) in local state.
- Show “Awaiting clarification” UI state instead of SSE connection error for this path.
- Submit clarification answer to backend resume endpoint.

**Acceptance Criteria**
- User can respond to clarification prompt in UI.
- UI state transitions: running -> clarification needed -> resumed running -> terminal.

**Verification**
1. Trigger clarification.
2. Enter answer in chat.
3. Confirm run resumes and completes/continues.

---

<a id="BACKEND-013"></a>

## BACKEND-013 [DONE] - Add run resume API for interrupt continuation
**Component:** BACKEND
**EPIC:** `EPIC-HITL-001`

**Goal**
- Provide explicit API to resume interrupted runs with user clarification text.

**Deliverables**
- `POST /api/runs/:runId/resume` endpoint.
- Request includes interrupt context + answer text.
- Resume executes graph continuation (`Command(resume=...)`) and continues SSE updates on same run.

**Acceptance Criteria**
- Valid resume request transitions run back to `running`.
- Invalid/expired interrupt returns clear `400/404`.

**Verification**
1. Trigger clarification interrupt.
2. Call resume endpoint with answer.
3. Confirm run continues and emits subsequent events.

---

<a id="QA-003"></a>

## QA-003 [DONE] - Add HITL clarification/resume regression checklist
**Component:** QA
**EPIC:** `EPIC-HITL-001`

**Goal**
- Ensure clarification workflows remain stable as chat/map features evolve.

**Deliverables**
- Checklist covering:
  - clarification event emission
  - UI clarification prompt rendering
  - resume API success/failure cases
  - resumed SSE stream continuity

**Acceptance Criteria**
- HITL path passes from initial run to resumed completion.
- No false “SSE connection error” shown for expected clarification flow.

**Verification**
1. Execute scripted clarification scenario.
2. Validate event timeline and UI states.
3. Record defects with event traces.

---

## EPIC-RENDER-001 - Agent Output Render Compatibility
**Feature Goal**
- Ensure agent-generated output files are transformed into map-consumable sources so layers reliably appear on MapLibre.

**Priority**
- Immediate / blocking for visibility of generated GeoParquet outputs in current POC.

---

<a id="BACKEND-014"></a>

## BACKEND-014 [DONE] - Normalize output types for layer generation
**Component:** BACKEND
**EPIC:** `EPIC-RENDER-001`

**Goal**
- Make backend tolerant to output type variants from agents (`GEOPARQUET` vs `GEOPARQUET_LAYER`, etc.).

**Deliverables**
- Output type normalization helper in run output plumbing.
- Normalize at least:
  - `GEOPARQUET`, `GEOPARQUET_LAYER`
  - `GEOTIFF`, `GEOTIFF_LAYER`
- Unknown types produce clear warning/log and safe fallback behavior.

**Acceptance Criteria**
- Both normalized GeoParquet labels follow same mapping path.
- No silent drop of valid output due to naming variant.

**Verification**
1. Inject mocked outputs with both naming variants.
2. Confirm layer registration path executes for both.
3. Confirm logs are emitted for unknown labels.

---

<a id="BACKEND-015"></a>

## BACKEND-015 [DONE] - Add POC GeoParquet -> GeoJSON conversion for map rendering
**Component:** BACKEND
**EPIC:** `EPIC-RENDER-001`

**Goal**
- Convert GeoParquet outputs to map-consumable GeoJSON sources in POC so MapLibre can display generated vector features.

**Deliverables**
- Conversion step in output-layer registration pipeline:
  - input: GeoParquet artifact path
  - output: GeoJSON artifact path
- Register converted artifact and set `LayerDescriptor.source` to converted GeoJSON URL.
- Keep original artifact registration (for audit/download) if needed.

**Acceptance Criteria**
- Agent-generated GeoParquet output appears as visible features on map.
- `layer_created` emitted after converted source is ready.

**Verification**
1. Run prompt that generates GeoParquet output.
2. Confirm converted GeoJSON artifact exists.
3. Confirm UI map renders resulting features.

---

<a id="QA-004"></a>

## QA-004 [DONE] - Add render-compatibility regression checks for generated outputs
**Component:** QA
**EPIC:** `EPIC-RENDER-001`

**Goal**
- Prevent regressions where outputs are created but not renderable on map.

**Deliverables**
- Checklist covering:
  - GeoParquet output generation
  - conversion artifact creation
  - `layer_created` sequencing
  - visible rendering on map

**Acceptance Criteria**
- End-to-end generated vector output is visible on map in POC.
- Failure cases produce actionable backend logs.

**Verification**
1. Execute generated-output scenario.
2. Validate conversion + layer descriptor source.
3. Confirm map visibility and capture traces.

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

## EPIC-LAYERSHOW-001 - Agent-Driven Layer Showing
**Feature Goal**
- When a user asks the agent to show a known GIS layer, that layer should become visible on the map without manual backend seeding.

**Scope**
- Backend action contract for show-layer intent
- Agent output contract for show-layer actions
- Catalog resolution/import plumbing
- SSE update events + UI handling

---

<a id="BACKEND-010"></a>

## BACKEND-010 [TODO] - Implement `show_layer(...)` service capability (+ production endpoint)
**Component:** BACKEND
**EPIC:** `EPIC-LAYERSHOW-001`

**Goal**
- Add a first-class backend service action to show an existing catalog/session layer by identifier, instead of relying on implicit side effects.

**Deliverables**
- `show_layer(...)` service method as source-of-truth implementation.
- Service input accepts one of:
  - `catalogItemId` (global catalog identity), or
  - `layerId` (already imported session layer).
- Service behavior:
  - if `catalogItemId` not in session: import/register artifact/create session layer
  - set target layer `visible=true`
  - return resolved `LayerDescriptor`
- Production API recommendation:
  - expose `POST /api/sessions/:sessionId/layers/show` on top of `show_layer(...)`.
  - For POC, endpoint can be deferred while AGENT flow calls service directly.

**Acceptance Criteria**
- Calling service with valid `catalogItemId` creates/returns visible input layer.
- Calling service with existing `layerId` toggles to visible.
- Invalid IDs return `404` with clear message.

**Verification**
1. Create session.
2. Call `show_layer(...)` with valid `catalogItemId`.
3. Verify returned layer has `visible=true`.
4. Call `GET /api/sessions/:sessionId/layers` and confirm layer exists.

---

<a id="AGENT-003"></a>

## AGENT-003 [TODO] - Extend agent/run contract for show-layer actions
**Component:** AGENT
**EPIC:** `EPIC-LAYERSHOW-001`

**Goal**
- Let agent output structured show-layer actions so backend can deterministically perform map updates.

**Deliverables**
- Add action payload shape in run processing, e.g.:
  - `{\"action\":\"show_layer\",\"catalog_item_id\":\"...\"}`
  - `{\"action\":\"show_layer\",\"layer_id\":\"...\"}`
- Update run execution path to detect actions and invoke backend show-layer service flow.
- Add guardrails so malformed actions do not crash runs.

**Acceptance Criteria**
- Agent-produced `show_layer` action triggers visible layer change in session.
- Invalid action payload emits clear run error event without process crash.

**Verification**
1. Trigger run with mocked/controlled agent action output.
2. Confirm backend invokes show-layer action path.
3. Confirm session layers reflect visible target layer.

---

<a id="BACKEND-011"></a>

## BACKEND-011 [TODO] - Emit `layer_updated` SSE event for visibility/state changes
**Component:** BACKEND
**EPIC:** `EPIC-LAYERSHOW-001`

**Goal**
- Stream explicit non-creation layer changes so UI can update map state without full polling reload.

**Deliverables**
- Add SSE event type: `layer_updated`.
- Emit `layer_updated` on visibility/state updates from:
  - show-layer endpoint
  - layer patch endpoint
  - run-driven actions
- Event payload includes at least:
  - `layerId`
  - changed fields (e.g., `visible`)

**Acceptance Criteria**
- Visibility updates emit `layer_updated` in run/session streams.
- Existing `layer_created` behavior remains unchanged.

**Verification**
1. Toggle layer visibility via API.
2. Confirm SSE includes `layer_updated` with expected payload.
3. Confirm no duplicate `layer_created` for pure updates.

---

<a id="UI-006"></a>

## UI-006 [TODO] - Handle show-layer and `layer_updated` events in map state
**Component:** UI
**EPIC:** `EPIC-LAYERSHOW-001`

**Goal**
- Ensure map and layer panel respond correctly when agent requests showing existing layers.

**Deliverables**
- Chat/SSE handler updates local layer state on `layer_updated`.
- On `show_layer`-driven results, UI either:
  - applies patch directly from event payload, or
  - fetches updated descriptor and patches state.
- Minimize full list reloads when only one layer changed.

**Acceptance Criteria**
- Asking agent to “show hotspot 2025” results in visible layer on map.
- Layer panel visibility checkbox reflects latest state.
- UI remains stable under repeated show/hide operations.

**Verification**
1. Start session and chat request for a known layer.
2. Observe streamed updates.
3. Confirm map visibility and checkbox state update correctly.

---

<a id="QA-002"></a>

## QA-002 [TODO] - Add EPIC-LAYERSHOW-001 regression checklist
**Component:** QA
**EPIC:** `EPIC-LAYERSHOW-001`

**Goal**
- Prevent regressions in agent-driven map layer visibility behavior.

**Deliverables**
- Checklist covering:
  - show by `catalogItemId`
  - show by existing `layerId`
  - repeated show requests
  - invalid IDs/payloads
  - SSE event sequence (`message/tool_*`, `layer_created`, `layer_updated`, terminal)

**Acceptance Criteria**
- All checklist scenarios pass in local POC run.
- Failures map to actionable bug reports with API traces.

**Verification**
1. Execute checklist against clean environment.
2. Capture network traces and SSE logs.
3. Record pass/fail and open follow-up items.

---

<a id="BACKEND-009"></a>

## BACKEND-009 [TODO] - Add run resume/reconnect by `runId`
**Component:** BACKEND

**Goal**
- Allow UI to reconnect to in-flight or completed runs without losing progress visibility.

**Deliverables**
- Stable run lookup + stream resume behavior by `runId`.
- `GET /api/runs/:runId` and `GET /api/runs/:runId/stream` support reconnect after UI refresh.

**Acceptance Criteria**
- If UI disconnects during a run, reconnecting with same `runId` resumes visibility of state/events.
- Completed runs can still be queried for terminal status and summary metadata.

**Verification**
1. Start a run and capture `runId`.
2. Disconnect UI or refresh page mid-run.
3. Reconnect using same `runId` and verify continued status visibility to terminal state.

---

<a id="UI-005"></a>

## UI-005 [TODO] - Add long-running notice (10 minutes) without aborting run
**Component:** UI

**Goal**
- Improve operator awareness for long jobs while preserving completion-oriented behavior.

**Deliverables**
- Non-blocking chat notice when a run exceeds 10 minutes.
- No client-side cancellation/timeout triggered by this notice.

**Acceptance Criteria**
- At 10 minutes, UI shows a clear “still running” informational message.
- SSE/run tracking continues normally and can still reach `done`/`error`.

**Verification**
1. Simulate or run a long job (>10 minutes).
2. Confirm the notice appears at approximately 10 minutes.
3. Confirm run continues and terminal event is still processed.

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

---

<a id="BACKEND-016"></a>

## BACKEND-016 [TODO] - Add configurable container-path to host-path mapping for artifacts (low priority)
**Component:** BACKEND
**Priority:** Low

**Goal**
- Avoid hardcoded `/data -> ./data` assumptions when resolving agent-generated artifact paths from container execution.

**Deliverables**
- Path resolver that maps container output paths to host filesystem paths using runtime settings/config.
- Support configurable mapping entries (for example container prefix + host mount dir).
- Clear error/log when path cannot be resolved safely.

**Acceptance Criteria**
- Artifact resolution works for non-default mount configurations.
- Existing default behavior remains backward-compatible.

**Verification**
1. Configure non-default container/host mount mapping in settings.
2. Generate output path from agent as container path.
3. Confirm backend resolves correct host path and registers artifact successfully.
