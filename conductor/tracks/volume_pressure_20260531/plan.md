# Implementation Plan: Volume Pressure Logic

## Phase 0: Self-Assessment Infrastructure [checkpoint: 76d5e1d]
- [x] Task: Create `tests/gate_checks.py` to automate comparison against Run 74 (Baseline: 372s, full metadata).
- [x] Task: Integrate `gate_checks.py` into the end of `main.py` to provide immediate pass/fail signal.
- [x] Task: Conductor - User Manual Verification 'Self-Assessment Infrastructure' (Protocol in workflow.md)

## Phase 1: Environment & Baseline [checkpoint: a5f3baf]
- [x] Task: Audit current `ai_client.py` and `main.py` duration gates.
- [x] Task: Create a baseline integration test to measure current segment/word averages.
- [x] Task: Conductor - User Manual Verification 'Environment & Baseline' (Protocol in workflow.md)

## Phase 2: Core Logic Update (TDD) [checkpoint: a5261c7]
- [x] Task: Write failing unit tests for `validate_broadcast` requiring 12-15 segments.
- [x] Task: Update `validate_broadcast` in `ai_client.py` to pass the new segment count requirement.
- [x] Task: Refactor the system prompt in `_build_prompt` to demand higher volume (12-15 segments, >100 words/segment).
- [x] Task: Update the `main.py` duration constants to align with production targets (600s).
- [x] Task: Conductor - User Manual Verification 'Core Logic Update' (Protocol in workflow.md)


## Phase 3: Resilience & Final Validation
- [ ] Task: Verify JSON Healer performance with longer AI outputs.
- [ ] Task: Execute a full local run (`npm run start`) to confirm 10-minute target achievement.
- [ ] Task: Conductor - User Manual Verification 'Resilience & Final Validation' (Protocol in workflow.md)
