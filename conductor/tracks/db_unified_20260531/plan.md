# Implementation Plan - Unified Database Support

## Phase 1: Serve Scripts & Backend Validation
- [x] Task: Create failing tests for `sync_config.py` ensuring it generates correct `config.js` for both modes. 28793bd
- [~] Task: Update `package.json` with `serve:sqlite` and `serve:supabase`.
- [ ] Task: Verify that running `serve:sqlite` correctly populates `config.js` with local data.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: UI Representation for Local Artifacts
- [ ] Task: Create a failing test for `app.js` that verifies `local://` URI resolution.
- [ ] Task: Refactor `app.js` to handle `local://` URIs for audio and video.
- [ ] Task: Update `buildDetail` in `app.js` to render local audio/video if found.
- [ ] Task: Ensure the UI displays a clear "LOCAL MODE" or "SUPABASE MODE" indicator.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Final Integration & Cleanup
- [ ] Task: Verify end-to-end flow for both `serve:sqlite` and `serve:supabase`.
- [ ] Task: Ensure all Quality Gates are met.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
