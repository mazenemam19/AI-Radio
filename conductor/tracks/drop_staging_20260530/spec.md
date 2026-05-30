# Track Specification: Drop Staging Environment ('Binary Model')

## 🎯 Purpose
To simplify the Echo broadcast suite by removing the redundant "Staging" environment and consolidating all development and production logic into a clean binary pole: Local (Shielded) and Production (Premium).

## 📋 Requirements

### 1. Environment Consolidation
- **Decommission Staging:** Remove all logical branches that reference the `staging` environment.
- **Binary Architecture:** 
    - **Local:** Strictly SQLite + Shielded AI (Gemini/Edge).
    - **Production:** Strictly Supabase + Premium AI (Groq/Mistral).
- **Cleanup Credentials:** Remove `STAGING_SUPABASE_*` variable logic from the codebase.

### 2. Tooling Refactor (`package.json`)
- **Delete Obsolete Scripts:** Remove `dev:staging` and `sync:staging`.
- **Harden Dry-Run:** Refactor `npm run dev:dry` to execute `python main.py --env production --dry-run` to ensure real infrastructure is tested without triggering a broadcast.

### 3. Codebase Cleanup
- **`db_client.py`:** Remove the staging credential loader and switch-case.
- **`sync_config.py`:** Remove staging environment sync logic.
- **`main.py`:** Simplify the environment selection logic.
- **`verify_system.py`:** Remove the "Environment Firewall" test as it's no longer necessary with a single remote environment.

### 4. Documentation Synchronization
- **`ARCHITECTURE.md`:** Convert all logic tables to a dual-column format (Production vs. Local).
- **`README.md`:** Remove staging setup instructions.
- **Feature Specs:** Update all specs to reflect the binary model.

## ✅ Acceptance Criteria
1. `npm run dev:staging` no longer exists.
2. `npm run dev:dry` successfully connects to the Production database (in dry-run mode).
3. All project documentation is strictly binary (Local/Prod).
4. System health check passes without referencing staging.
