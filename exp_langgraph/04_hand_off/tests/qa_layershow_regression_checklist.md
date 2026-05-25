# QA-002 EPIC-LAYERSHOW-001 Regression Checklist

Use this checklist to verify agent-driven and API-driven layer showing behavior.

## Preconditions
- Backend running: `python main_api.py`
- UI running: `cd ui && npm run dev`
- Data files required by `domain/gis_catalog.py` are present/mounted.

## Scope
This checklist covers:
1. Show layer by catalog identity/artifact.
2. Show existing session layer by layer id.
3. Repeated show requests (idempotent behavior).
4. Invalid selector payloads and not-found responses.
5. SSE event behavior for `layer_updated`.
6. UI/backend consistency for visibility toggles.

## Manual Checklist
1. Start a new session in UI.
2. Import one catalog item from Catalog panel.
3. Confirm imported layer appears under Input Layers and is visible on map.
4. Hide the layer using layer toggle; confirm map hides it.
5. Show it again using agent prompt (for example: "show hotspot 2024").
6. Confirm layer becomes visible again without duplicate layer entries.
7. Repeat the same show prompt again; confirm still one session layer entry.
8. Trigger a run that generates a new output artifact/layer.
9. Confirm output layer appears under Agent Output Layers and is visible.

## API/SSE Checks
1. `POST /api/sessions/:sessionId/layers/show` with valid artifact resolves to visible layer.
2. `POST /api/sessions/:sessionId/layers/show` with invalid selector returns `400`.
3. `POST /api/sessions/:sessionId/layers/show` with unknown artifact/layer returns `404`.
4. `PATCH /api/layers/:layerId` emits `layer_updated` and persists state.
5. `POST /api/sessions/:sessionId/layers/import` emits `layer_updated`.
6. Output-producing run (actions path) emits `layer_updated` when layer visibility/state changes.

## Expected SSE Sequence (Typical)
1. `message`
2. `tool_start`
3. zero or more `tool_end` intermediate updates
4. `layer_updated` (show/import/toggle/action-driven visibility/state paths)
5. terminal event: `done` or actionable `error`

## Evidence to Capture
- Browser network traces for:
  - `/api/sessions/:id/layers/import`
  - `/api/sessions/:id/layers/show`
  - `/api/layers/:id` (PATCH/GET)
  - `/api/runs/:id/stream`
- Backend logs containing resolved show-layer path and SSE emissions.
- UI screenshots: layer panel + map before/after show/hide operations.
