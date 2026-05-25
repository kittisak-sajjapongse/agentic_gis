# QA-004 Render Compatibility Checklist

Use this checklist to verify that agent-generated vector outputs are map-renderable in the POC.

## Preconditions
- Backend running: `python main_api.py`
- UI running: `cd ui && npm run dev`
- HITL flow working (if clarification is expected)

## Manual E2E Checklist
1. Start a new session in UI.
2. Submit a prompt that generates a vector output (GeoParquet).
3. If clarification is requested, resume run with an answer.
4. Confirm backend emits `layer_updated` for action-driven layer visibility/state updates.
5. Confirm generated layer appears in Layer Panel.
6. Confirm generated layer is visible on MapLibre map.
7. Toggle visibility off/on and confirm map updates.

## Artifact/Contract Checks
1. Confirm generated run output file exists under `data/` as `.parquet`.
2. Confirm converted `.geojson` artifact is created for rendering path.
3. Confirm `GET /api/layers/:layerId` source points to `/api/artifacts/:artifactId/content` for converted GeoJSON source.

## Negative Checks
1. If output type label variant is used (`GEOPARQUET` vs `GEOPARQUET_LAYER`), layer creation still succeeds.
2. If unknown output label is used, backend logs warning and applies suffix fallback.

## Evidence to Capture
- UI screenshots (layer list + map)
- Backend logs for `layer_updated` and any fallback warnings
- Relevant network traces (`/stream`, `/layers/:id`, `/artifacts/:id/content`)
