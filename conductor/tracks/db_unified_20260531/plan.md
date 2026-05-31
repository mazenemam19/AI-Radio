# Implementation Plan - Unified Database Support

## Phase 1: Serve Scripts & Backend Validation [checkpoint: eebd4ff]
- [x] Task: Create failing tests for `sync_config.py` ensuring it generates correct `config.js` for both modes. 28793bd
- [x] Task: Update `package.json` with `serve:sqlite` and `serve:supabase`. 80ececf
- [x] Task: Verify that running `serve:sqlite` correctly populates `config.js` with local data. d90c224
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md) eebd4ff

## Phase 2: UI Representation for Local Artifacts [checkpoint: 67c222d]
- [x] Task: Create a failing test for `app.js` that verifies `local://` URI resolution. d75ea96
- [x] Task: Refactor `app.js` to handle `local://` URIs for audio and video. 44a4a84
- [x] Task: Update `buildDetail` in `app.js` to render local audio/video if found. 44a4a84
- [x] Task: Ensure the UI displays a clear "LOCAL MODE" or "SUPABASE MODE" indicator. 44a4a84
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md) 67c222d

## Phase 3: Final Integration & Cleanup
- [~] Task: Verify end-to-end flow for both `serve:sqlite` and `serve:supabase`.
- [ ] Task: Ensure all Quality Gates are met.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
