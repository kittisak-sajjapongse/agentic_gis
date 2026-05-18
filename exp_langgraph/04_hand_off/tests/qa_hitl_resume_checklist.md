# QA-003 HITL Clarification/Resume Checklist

Use this checklist for manual verification of HITL behavior in the UI.

## Preconditions
- Backend running: `python main_api.py`
- UI running: `cd ui && npm run dev`
- Prompt likely to trigger clarification question.

## Checklist
1. Start a new chat run from UI.
2. Confirm chat receives `clarification_required` behavior (human question shown).
3. Confirm UI state shows "Awaiting clarification" and does not show false transport error.
4. Enter clarification answer in the chat input.
5. Confirm UI calls `POST /api/runs/:runId/resume`.
6. Confirm run returns to running state and continues streaming events.
7. Confirm run reaches terminal status (`done` or actionable `error`).
8. If output layers are generated, confirm `layer_created` is processed by UI.

## Negative Cases
1. Resume with wrong `interruptId` should return HTTP 400.
2. Resume for non-existing `runId` should return HTTP 404.
3. Resume when run context expired should return HTTP 409 (POC limitation).

## Evidence to Capture
- Browser network logs for `/stream` and `/resume` calls.
- Backend logs around interrupt/resume events.
- Final run status from `GET /api/runs/:runId`.
