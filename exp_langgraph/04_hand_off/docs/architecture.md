# UI + Backend + Agent Architecture

## 1) Overall Architecture

This document describes a proof-of-concept (POC) architecture for adding a web UI to `04_hand_off` so users can:
- Chat with agents
- Visualize input GIS layers
- Visualize agent-produced output layers on a map

The architecture has three main pieces:
1. UI (React + TypeScript)
2. Backend application (Python service in this repository)
3. Agent runtime (LangGraph + existing agent/tool graph)

### 1.1 Responsibilities by Piece

#### UI (React + TypeScript)
- Render map and layer controls
- Render chat panel and stream agent responses
- Keep session state (messages, runs, layers, map view)
- Call backend APIs only (never directly read local disk)

#### Backend (Python service)
- Expose HTTP APIs + SSE stream to the UI
- Translate UI requests into graph/agent execution
- Manage layer catalog and artifacts
- Serve GIS artifacts from local filesystem (POC)
- Emit structured events (`message`, `tool_start`, `layer_created`, etc.)

#### Agent Runtime (LangGraph + agents/tools)
- Execute agent workflow (input retrieval, tool calls, output production)
- Produce semantic outputs and layer artifacts
- Return deterministic layer metadata contracts for UI rendering

### 1.2 Architecture Illustration

```text
+---------------------------------------------------------------+
|                         Browser (UI)                          |
|                                                               |
|  +--------------------+       +----------------------------+  |
|  | Map Pane           |       | Chat Pane (assistant-ui)   |  |
|  | - MapLibre map     |       | - Prompt input             |  |
|  | - Layer tree       |       | - Streaming messages       |  |
|  | - Visibility/style |       | - Tool/run status          |  |
|  +----------+---------+       +-------------+--------------+  |
|             |                               |                 |
+-------------|-------------------------------|-----------------+
              | HTTP/1.1 or HTTP/2            | HTTP/1.1 text/event-stream
              | REST JSON request/response     | SSE server push events
              v                               v
+---------------------------------------------------------------+
|                  Python Backend API Layer                     |
|                                                               |
|  Endpoints:                                                   |
|  - POST /api/sessions                                         |
|  - GET  /api/sessions/:id/layers                              |
|  - POST /api/sessions/:id/chat                                |
|  - GET  /api/runs/:id/stream   (SSE)                          |
|  - GET  /api/layers/:id                                        |
|  - GET  /api/artifacts/:id/content                             |
|                                                               |
|  Services:                                                     |
|  - Session service                                             |
|  - Layer registry                                              |
|  - Artifact provider (local now, S3-compatible later)         |
+----------------------------+----------------------------------+
                             |
                             | in-process Python invocation
                             | runtime/container -> graph callable
                             | function/method calls + typed models
                             v
+---------------------------------------------------------------+
|                  Agent Runtime (LangGraph)                    |
|                                                               |
|  graphs/ + agents/ + tools/ + domain/                         |
|  - input retrieval agent                                       |
|  - output producer agent                                       |
|  - tool executor node                                          |
|  - GIS catalog tools                                           |
|                                                               |
|  Outputs: messages, tool events, layer descriptors, artifacts |
+----------------------------+----------------------------------+
                             |
                             | artifact read/write via provider
                             | POC: POSIX filesystem I/O (read/write files)
                             | Prod: S3 API (PutObject/GetObject) via SDK
                             v
+---------------------------------------------------------------+
|                     Storage (POC: Local FS)                   |
|                      ./data, generated outputs                |
+---------------------------------------------------------------+
```

Channel legend:
- UI -> Backend REST: synchronous HTTP JSON APIs for command/query operations.
- UI -> Backend SSE: long-lived HTTP stream for incremental run events.
- Backend -> Agent Runtime: in-process invocation inside same Python service (no network hop in POC).
- Agent Runtime <-> Storage: artifact provider abstraction; local file I/O now, object storage API later.

### 1.3 Layering Alignment with `AGENTS.md`

- `domain/`: contracts + shared state + static datasets
- `agents/`: LLM behavior only
- `tools/`: integrations/execution adapters
- `graphs/`: topology/routing
- `runtime/`: dependency construction/config
- Entry points remain thin (`main.py`, `main_cli.py`)

The UI is added as a separate subdirectory (`ui/`) to keep backend architecture intact.

### 1.4 Persistent State Storage (POC)

The backend now includes a small persistence abstraction for application state
so restart does not lose active session metadata and layer/run registries.

Key points:
1. API code depends on `PersistenceStore` interface (not concrete backend type).
2. Current implementation is `JsonPersistenceStore` (file-backed snapshot).
3. Backend is selected by config (`PERSISTENCE_BACKEND`, currently `json`).
4. Snapshot file path is configured by `STATE_FILE`.

Current persisted state domains:
1. `sessions`
- `sessionId`, `status`, `createdAt`, `lastRunId`

2. `runs`
- `runId`, `sessionId`, `status`, `startedAt`, `finishedAt`
- `error`, `declineMessage`
- `pendingInterruptId`, `pendingQuestion`

3. `layers_by_session`
- Session-keyed list of `LayerDescriptor` records
- Includes map-facing metadata:
  - `id`, `name`, `kind`, `source`, `style`
  - `visible`, `opacity`, `bounds`
  - `origin`, `createdByRunId`, `createdAt`

4. `artifacts`
- `artifact_id`, absolute `path`, `content_type`, `size_bytes`
- Used by `/api/artifacts/:id/content` for content streaming

Not persisted:
1. In-memory run execution objects (`_graphs`, `_configs`) used only for active
   HITL resume in the current process.
2. SSE subscriber queues/connections.

Lifecycle:
1. On startup: backend loads persisted snapshot and reconstructs service state.
2. On mutation: services invoke `on_change` callback and persist a fresh
   snapshot atomically.
3. On restart: UI can continue from existing session/layer/run metadata using
   normal APIs.

---

## 2) API Design

### 2.1 API Principles

1. UI talks only to backend APIs
2. Use typed contracts for layers/events
3. Use SSE for incremental chat/tool/run updates
4. Keep artifact access behind backend URLs so storage backend can change later

### 2.2 Core Data Contracts

### 2.2.1 Two API Paths: `layers` vs `artifacts`

The architecture intentionally separates metadata from raw content:

1. `layers` path (`/api/sessions/:sessionId/layers`, `/api/layers/:layerId`)
- Returns `LayerDescriptor` metadata used by UI state and map configuration.
- Includes logical fields such as `name`, `kind`, `style`, `visible`, `origin`, `bounds`.
- Contains a source reference URL (usually artifact-backed), but does not return large file bytes.

2. `artifacts` path (`/api/artifacts/:artifactId/content`)
- Returns raw bytes/content stream for registered artifacts.
- Used by map/data consumers when actual file content is needed.
- Backed by `ArtifactProvider` (local filesystem in POC; S3-compatible storage later).

Ownership boundary:
- Layer registry/service owns map/business metadata.
- Artifact provider owns storage lookup and content streaming.

Design principle: separate presentation identity from storage identity.
- `layerId` identifies a map-facing logical layer (style, visibility, origin, UX state).
- `artifactId` identifies stored content bytes and storage metadata.
- They are intentionally different IDs because they model different concerns.

Why this separation matters:
1. Backend can change storage implementation (local FS -> S3-like) without changing layer contracts.
2. Multiple layers can reference the same artifact with different map styles/visibility.
3. A layer can keep stable UI identity while its underlying artifact version/source changes.
4. Layer APIs remain focused on map semantics; artifact APIs remain focused on byte serving.

Request flow:
1. UI gets layer descriptors from `layers` endpoints.
2. UI reads `source.url` from each descriptor.
3. UI/map fetches content from `artifacts` endpoint when rendering/loading data.

Render compatibility note (important for generated outputs):
- Raw GeoParquet bytes are not directly consumable by MapLibre `geojson` sources.
- POC rendering path should convert GeoParquet outputs into GeoJSON artifacts
  before creating `LayerDescriptor.source` for map display.
- Original GeoParquet can still be retained as raw artifact for download/audit.

### 2.2.2 Show-Layer Capability (Service First)

To support requests like “show hotspot 2025 on map,” the backend should expose a
domain capability named `show_layer(...)` in the service layer.

`show_layer(...)` responsibilities:
1. Resolve target by `catalogItemId` or existing `layerId`.
2. If needed, import/register artifact and create session layer.
3. Set layer `visible=true` idempotently.
4. Return the resolved/updated `LayerDescriptor`.

Design decision:
- Source of truth is the service method, not route handlers.
- API handlers and run orchestration both call the same service method.

Production recommendation:
- Expose `POST /api/sessions/:sessionId/layers/show` as an explicit command API
  backed by `show_layer(...)`.
- Keep `GET /api/catalog` + `POST /layers/import` for manual discovery/import flows.

Visibility source-of-truth rule:
- Catalog is discovery-only (`GET /api/catalog`).
- Map visibility state is session-layer state (backend-owned), not catalog state.
- UI show/hide toggles should call backend (`PATCH /api/layers/:layerId`).
- UI should react to `layer_updated` SSE and patch local map/layer state.
- `POST /api/sessions/:sessionId/layers/show` is for explicit server-side
  show command (agent-driven or API-driven), not required after every import.

POC note:
- The endpoint can be deferred while run orchestration calls `show_layer(...)`
  directly in-process.

#### LayerDescriptor

```json
{
  "id": "lyr_out_001",
  "name": "Flood-prone Roads",
  "kind": "geojson",
  "source": { "type": "geojson", "url": "/api/artifacts/art_001/content" },
  "style": {
    "preset": "line-default",
    "paint": { "line-color": "#d62728", "line-width": 3 }
  },
  "visible": true,
  "opacity": 1.0,
  "bounds": [-79.8, 43.1, -78.9, 43.9],
  "origin": "agent_output",
  "createdByRunId": "run_456",
  "createdAt": "2026-05-13T12:10:22Z"
}
```

#### AgentEvent (SSE payload)

```json
{
  "type": "layer_created",
  "runId": "run_456",
  "sessionId": "sess_123",
  "timestamp": "2026-05-13T12:10:20Z",
  "payload": {
    "layerId": "lyr_out_001"
  }
}
```

### 2.3 API and SSE Table

| Method / Stream | Path | Purpose | Request Example | Response / Event Example |
|---|---|---|---|---|
| `POST` | `/api/sessions` | Create a new UI session | `{}` | `{ "sessionId": "sess_123", "createdAt": "2026-05-13T12:00:00Z" }` |
| `GET` | `/api/sessions/:sessionId` | Get session metadata/status | N/A | `{ "sessionId": "sess_123", "status": "active", "lastRunId": "run_456" }` |
| `GET` | `/api/sessions/:sessionId/layers` | List all layers in session | N/A | `{ "layers": [ ...LayerDescriptor ] }` |
| `POST` | `/api/sessions/:sessionId/chat` | Submit user message and start run | `{ "message": "Find burnscar overlap", "context": { "selectedLayerIds": ["lyr_a"] } }` | `{ "runId": "run_456", "streamUrl": "/api/runs/run_456/stream" }` |
| `GET` | `/api/runs/:runId` | Get run metadata and current status | N/A | `{ "runId": "run_456", "status": "running", "startedAt": "..." }` |
| `GET` (SSE) | `/api/runs/:runId/stream` | Stream run/chat/tool/layer events | N/A | `event: message` + `data: {...}` (see §2.4) |
| `POST` | `/api/runs/:runId/resume` | Resume interrupted run with clarification answer (HITL) | `{ "interruptId":"intr_1", "answer":"Use 2025 only" }` | `{ "runId":"run_456", "status":"running" }` |
| `GET` | `/api/layers/:layerId` | Fetch one layer descriptor | N/A | `{ ...LayerDescriptor }` |
| `PATCH` | `/api/layers/:layerId` | Update UI-controlled layer state (visibility, opacity, style override) | `{ "visible": false, "opacity": 0.5 }` | `{ ...LayerDescriptor }` |
| `GET` | `/api/artifacts/:artifactId/content` | Retrieve raw artifact data for map source | N/A | Content stream (GeoJSON/tiles/raster/etc.) |
| `GET` | `/api/catalog` | Optional: list available local GIS datasets to add as input layers | N/A | `{ "items": [{ "id":"cat_1", "name":"rainfall_2025_01" }] }` |
| `POST` | `/api/sessions/:sessionId/layers/import` | Optional: import catalog item into session as input layer | `{ "catalogItemId": "cat_1" }` | `{ "layerId": "lyr_input_77" }` |
| `POST` | `/api/sessions/:sessionId/layers/show` | Explicit server-side show command for an existing session layer or catalog-resolvable artifact | `{ "artifact": "/data/hotspot_2025.parquet" }` | `{ ...LayerDescriptor, "visible": true }` |

### 2.4 SSE Event Types

Backend should emit these event types from `/api/runs/:runId/stream`:

1. `message`
- Agent/user-facing text updates

2. `tool_start`
- Tool execution started

3. `tool_end`
- Tool execution completed (success/failure summary)

4. `layer_created`
- A new map layer is available
- UI should call `GET /api/layers/:layerId` and render it

5. `layer_updated`
- Existing session layer metadata/state changed (`visible`, `opacity`, `style`, etc.)
- UI should patch local layer state directly from payload (`layerId`, `changed`)
- Emitted from:
  - `PATCH /api/layers/:layerId`
  - `POST /api/sessions/:sessionId/layers/show`
  - `POST /api/sessions/:sessionId/layers/import`
  - Run-driven `show_layer` actions

6. `clarification_required`
- Expected HITL interrupt (not failure) requiring user response.
- Payload should include `interruptId` and `question`.

7. `error`
- Recoverable/non-recoverable run errors

8. `done`
- Run completed

#### SSE event examples

```text
event: message
data: {"type":"message","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:00Z","payload":{"role":"assistant","text":"Running slope analysis..."}}
```

```text
event: tool_start
data: {"type":"tool_start","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:05Z","payload":{"tool":"analyze_slope","args":{"threshold":20}}}
```

```text
event: layer_created
data: {"type":"layer_created","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:20Z","payload":{"layerId":"lyr_out_001"}}
```

```text
event: layer_updated
data: {"type":"layer_updated","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:21Z","payload":{"layerId":"lyr_in_002","changed":{"visible":true}}}
```

```text
event: clarification_required
data: {"type":"clarification_required","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:22Z","payload":{"interruptId":"intr_1","question":"Which month in 2025 should be used?"}}
```

```text
event: done
data: {"type":"done","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:40Z","payload":{"status":"completed"}}
```

### 2.5 Request/Response Examples by Endpoint

#### `POST /api/sessions`
Purpose: Create a new session for one UI tab/user workflow.

Request:
```http
POST /api/sessions
Content-Type: application/json

{}
```

Response:
```json
{
  "sessionId": "sess_123",
  "createdAt": "2026-05-13T12:00:00Z"
}
```

#### `GET /api/sessions/sess_123`
Purpose: Retrieve session metadata and latest run pointer.

Response:
```json
{
  "sessionId": "sess_123",
  "status": "active",
  "lastRunId": "run_456"
}
```

#### `GET /api/sessions/sess_123/layers`
Purpose: Return current session layer registry used by map + layer panel.

Response:
```json
{
  "layers": [
    {
      "id": "lyr_roads",
      "name": "Road Network",
      "kind": "geojson",
      "source": { "type": "geojson", "url": "/api/artifacts/art_roads/content" },
      "style": { "preset": "line-default", "paint": { "line-color": "#1f77b4", "line-width": 2 } },
      "visible": true,
      "origin": "input",
      "createdByRunId": null,
      "createdAt": "2026-05-13T12:00:10Z"
    }
  ]
}
```

#### `GET /api/catalog`
Purpose: List globally available catalog items (discovery only; not yet session layers).

Response:
```json
{
  "items": [
    {
      "catalogItemId": "cat_001",
      "description": "Hotspots in Thailand for the year 2024",
      "file": "/data/hotspot_2024.parquet",
      "type": "GEOPARQUET",
      "country": "Thailand",
      "year": 2024
    }
  ]
}
```

#### `POST /api/sessions/sess_123/layers/import`
Purpose: Materialize a catalog item into this session as an input layer.

Request:
```json
{
  "catalogItemId": "cat_001"
}
```

Response:
```json
{
  "id": "lyr_in_001",
  "name": "Hotspots in Thailand for the year 2024",
  "kind": "geojson",
  "visible": true,
  "catalogItemId": "cat_001"
}
```

#### `POST /api/sessions/sess_123/layers/show`
Purpose: Explicitly show one target layer (agent-driven or API-driven command).

Request:
```json
{
  "artifact": "/data/hotspot_2024.parquet"
}
```

Response:
```json
{
  "id": "lyr_in_001",
  "name": "Hotspots in Thailand for the year 2024",
  "visible": true
}
```

#### `POST /api/sessions/sess_123/chat`
Purpose: Start a run for the user message; returns `runId` immediately.

Request:
```json
{
  "message": "Identify roads intersecting high rainfall areas and output a layer",
  "context": {
    "selectedLayerIds": ["lyr_roads", "lyr_rain_2025_01"]
  }
}
```

Response:
```json
{
  "runId": "run_456",
  "streamUrl": "/api/runs/run_456/stream"
}
```

#### `GET /api/runs/run_456`
Purpose: Poll current run status and terminal fields (error/decline/interrupt state).

Response:
```json
{
  "runId": "run_456",
  "sessionId": "sess_123",
  "status": "running",
  "startedAt": "2026-05-13T12:10:00Z",
  "finishedAt": null,
  "error": null
}
```

#### `GET /api/runs/run_456/stream` (SSE)
Purpose: Stream incremental run events (`message`, `tool_*`, `layer_*`, `clarification_required`, `done`, `error`).

Response stream example:
```text
event: message
data: {"type":"message","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:00Z","payload":{"status":"running"}}

event: layer_updated
data: {"type":"layer_updated","runId":"run_456","sessionId":"sess_123","timestamp":"2026-05-13T12:10:21Z","payload":{"layerId":"lyr_in_001","changed":{"visible":true}}}
```

#### `POST /api/runs/run_456/resume`
Purpose: Continue an interrupted HITL run with user answer for `interruptId`.

Request:
```json
{
  "interruptId": "intr_1",
  "answer": "Use March 2025 only"
}
```

Response:
```json
{
  "runId": "run_456"
}
```

#### `GET /api/layers/lyr_out_001`
Purpose: Fetch one layer descriptor by layer ID.

Response:
```json
{
  "id": "lyr_out_001",
  "name": "Roads in High Rainfall",
  "kind": "geojson",
  "source": { "type": "geojson", "url": "/api/artifacts/art_001/content" },
  "style": { "preset": "line-default", "paint": { "line-color": "#d62728", "line-width": 3 } },
  "visible": true,
  "origin": "agent_output",
  "createdByRunId": "run_456",
  "createdAt": "2026-05-13T12:10:21Z"
}
```

#### `PATCH /api/layers/lyr_out_001`
Purpose: Persist layer UI state changes (`visible`, `opacity`, `style`) in backend session state.

Request:
```json
{
  "visible": false,
  "opacity": 0.6
}
```

Response:
```json
{
  "id": "lyr_out_001",
  "visible": false,
  "opacity": 0.6
}
```

#### `GET /api/artifacts/art_001/content`
Purpose: Stream raw artifact bytes for map/data consumption (GeoJSON, TIFF, etc.).

Important identifier semantics:
- `artifactId` is the artifact registry identifier (for example `art_001`).
- `artifactId` is **not** `layerId`.
- One layer descriptor references one source URL, and that URL includes an
  artifact ID: `LayerDescriptor.source.url = /api/artifacts/{artifactId}/content`.

Lookup flow:
1. UI has a `layerId`.
2. UI fetches `GET /api/layers/{layerId}` (or reads it from session layer list).
3. UI reads `source.url` from the descriptor.
4. UI requests `GET /api/artifacts/{artifactId}/content` using that URL.

Coverage:
- Works for imported catalog layers and agent-created output layers.
- Backend artifact provider resolves the storage path (local FS in POC, S3-like in production).

Response:
```http
HTTP/1.1 200 OK
Content-Type: application/geo+json

{ "type": "FeatureCollection", "features": [] }
```

#### `GET /api/health`
Purpose: Health/readiness check for UI and local ops.

Response:
```json
{
  "status": "ok",
  "timestamp": "2026-05-13T12:00:00Z"
}
```

---

## 3) Proof-of-Concept Design

### 3.1 Technologies in POC

UI:
- React + TypeScript
- MapLibre GL JS for map rendering
- `assistant-ui` for chat panel components
- Optional state library: Zustand (or equivalent)

Backend:
- Existing Python application in this repository
- Existing LangGraph-based agent workflow
- HTTP API layer + SSE stream endpoint
- Local filesystem artifact storage (`data/` and generated outputs)

Agent stack:
- Existing `agents/`, `graphs/`, `tools/`, `domain/`, `runtime/` layering
- Reuse current tool execution patterns (no duplicate ad-hoc wrappers)

### 3.2 How POC Works End-to-End

1. User opens UI, UI creates session via `POST /api/sessions`.
2. UI loads current layers via `GET /api/sessions/:id/layers`.
3. User asks question in chat panel.
4. UI calls `POST /api/sessions/:id/chat` and subscribes to SSE stream URL.
5. Backend executes agent run in LangGraph.
6. Backend emits incremental events (`message`, `tool_start`, `tool_end`).
7. When output layer is produced, backend emits `layer_created`.
8. UI fetches new layer descriptor and adds it to MapLibre.
9. User toggles visibility/style in Layer Panel; UI persists via `PATCH /api/layers/:id` (backend is source of truth).
10. Backend emits `layer_updated`; UI patches layer state without full layer-list reload.
10. If run emits `clarification_required`, UI captures `interruptId`, prompts user, and calls `POST /api/runs/:runId/resume` to continue the same run.

### 3.3 Why `deck.gl` Is Excluded From Initial POC

- MapLibre alone covers baseline needs: display input/output layers, toggle visibility, simple styling.
- POC priority is integration speed and correctness of contracts/events.
- `deck.gl` can be added later when advanced rendering/performance needs appear.

---

## 4) Production Considerations (S3-Compatible Migration)

### 4.1 Goal

Move from local filesystem artifact serving to object storage with minimal UI and API changes.

### 4.2 Storage Abstraction Strategy

Define backend interface, for example:
- `ArtifactProvider.get_read_url(artifact_id)`
- `ArtifactProvider.put_artifact(...)`
- `ArtifactProvider.get_metadata(...)`

Implementations:
1. `LocalArtifactProvider` (POC)
2. `S3ArtifactProvider` (production)

UI continues using the same `LayerDescriptor.source` contract.

### 4.3 Migration Path (Minimal Change)

1. Keep API paths and payloads stable.
2. Switch backend provider binding in runtime config.
3. For production, `/api/artifacts/:id/content` may:
- Proxy object bytes, or
- Redirect to short-lived signed URL
4. Layer metadata schema does not change.
5. UI map source creation logic does not change.

### 4.4 Production Requirements Checklist

1. Security
- AuthN/AuthZ on all session/run/artifact endpoints
- Signed URLs with short TTL for direct object access
- Per-session and per-user access control

2. Reliability
- Durable run/layer metadata store (DB instead of in-memory)
- Retry/reconnect semantics for SSE
- Idempotent run creation keys if needed

3. Performance
- Pre-generate map-friendly outputs where needed (e.g., vector tiles)
- CDN in front of artifact reads
- Pagination for large layer catalogs

4. Observability
- Correlate `sessionId`, `runId`, `layerId` in logs
- Metrics for run duration, tool latency, layer generation failure rate

5. Data Governance
- Artifact lifecycle/retention policy
- Versioning for generated outputs
- Audit trail of user prompt -> run -> artifacts

---

## 5) UI Component Architecture

### 5.1 Component Tree

```text
AppShell
├─ TopBar (session status, connection health)
├─ LeftPanel
│  └─ LayerPanel
│     ├─ Input Layers group
│     └─ Agent Output Layers group
├─ Center
│  └─ MapPane (MapLibre)
└─ RightPanel
   └─ ChatPane (assistant-ui)
```

### 5.2 Frontend State Domains

1. Session state
- `sessionId`, connection status, active run

2. Chat state
- messages, streaming buffer, tool status timeline

3. Layer state
- descriptors, visibility, opacity, selection, ordering

4. Map state
- viewport, selected feature, hovered feature

### 5.3 UI Behavior Rules

1. On `layer_created`, fetch layer descriptor and append to output group.
2. On `error`, show inline run error in chat and keep existing layers untouched.
3. If SSE disconnects, show reconnect state and allow manual resume.

---

## 6) Backend Integration Notes for Current Repository

### 6.1 Recommended Placement (No boundary violations)

- `domain/state_models.py`
  - Add typed API/session/layer/event contracts if they become shared
- `tools/`
  - Keep artifact provider and GIS integration adapters here
- `graphs/`
  - Keep routing/orchestration only
- `runtime/container.py`
  - Wire dependencies (artifact provider, services)
- Entry points
  - Keep thin; only bootstrap web/CLI runtime

### 6.2 Compatibility With Existing GIS Data

Current local files in `data/` (e.g., `.parquet`, `.tif`) are backend-accessed only.
The backend should expose UI-ready sources:
- GeoJSON endpoint for vector-like outputs
- Raster/tile-serving endpoint for TIFF/COG datasets
- Catalog metadata endpoint for discoverability

---

## 7) Suggested Incremental Implementation Plan

1. Build minimal API skeleton: sessions, chat start, run status, SSE stream.
2. Add layer registry + `GET /layers` + `GET /layers/:id`.
3. Add artifact serving endpoint for local files.
4. Build React UI shell with map + layer panel + assistant-ui chat.
5. Wire SSE events to UI store and map updates.
6. Add persistence and auth guardrails.
7. Introduce storage abstraction and swap to S3-compatible provider.

---

## 8) Open Design Decisions

1. Backend web framework choice for new APIs (FastAPI/Flask/other).
2. Session persistence model (in-memory vs DB) for multi-user usage.
3. Preferred map source strategy for large raster/vector datasets (raw vs tiled).
4. Authentication approach for UI and API in production.
