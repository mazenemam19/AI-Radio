# Implementation Plan: Drop Staging Environment ('Binary Model')

## Phase 1: Codebase Refactor (Intent-Driven)
- [ ] Task: Refactor `db_client.py` to remove staging logic
    - [ ] Remove `staging` condition from `__init__` and credential loading
    - [ ] Unify connection logic: `env == "production"` triggers Supabase, otherwise SQLite
- [ ] Task: Refactor `sync_config.py` to remove staging logic
    - [ ] Ensure local dashboard can sync from Production Supabase data via `--env production`
- [ ] Task: Update `main.py` environment logic
    - [ ] Clarify defaults: `--env production` is now the only way to reach cloud infra
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Tooling & Test Cleanup
- [ ] Task: Update `package.json` scripts
    - [ ] Delete `sync:staging` and `dev:staging`
    - [ ] Refactor `dev:dry`: Update to `python main.py --env production --dry-run`
    - [ ] **NEW:** Refactor `dev:news` to support local news testing against cloud DB if needed
- [ ] Task: Clean up `verify_system.py`
    - [ ] Remove `test_environment_firewall` (Staging vs Prod check)
    - [ ] Ensure `Database Schema Sync` only compares Local vs Production
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Documentation Synchronization
- [ ] Task: Update core architecture and system docs
    - [ ] Update `ARCHITECTURE.md` (remove staging column, document Intent-Driven flow)
    - [ ] Update `SYSTEM.md` (codify Binary Model)
    - [ ] Update `README.md` (remove staging variables, document dev:dry as cloud portal)
- [ ] Task: Update all feature specifications
    - [ ] Review and update `specs/features/*.md` to reflect binary model
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
