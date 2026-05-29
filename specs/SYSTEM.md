# System Specification: AI Radio — Echo

This is the baseline "contract" for the Echo platform. It defines the foundational logic that all features must inherit.

## 🏗️ Core Architecture
- **Broadcast Pattern:** Mono-Topic Deep Dive (~10 minutes).
- **Client Logic:** Multi-environment aware (Local, Staging, Production).
- **Database:** Polyglot persistence (Supabase for Cloud, SQLite for Local) with exact-match schema verification.
- **Duration Tracking:** Automated show length calculation and database logging.

## 🛡️ Global Constraints
- **Deduplication:** Original Source Headline tracking with Threshold-2 Keyword Overlap.
- **Strict Provider Isolation:** Testing/Local sets (Google/Microsoft) MUST NOT overlap with Production sets (Groq/Mistral).
- **Resilient Multi-Tier Queue:** Implements a 6-tier failover strategy (Set A) to combat rate limits and ensure broadcast reliability.
- **Deep Observability:** Mandatory logging of raw model outputs, quality metrics, and specific error codes (429, 413, etc.).
- **Fail-Fast Integrity:** Placeholder scripts are prohibited. System must ABORT (code 1) if AI quality thresholds are not met.
- **Persona:** Jon Stewart-style satirical performance with mandatory rhythm shifts and numerical suppression.

## 🔗 Feature Index
Current active modules documented in `specs/features/`:
- [001: Hybrid Media Player](./features/001-hybrid-player.md)
- [002: Neural Art Engine](./features/002-neural-art.md)
- [003: Satirical Performance logic](./features/003-satirical-performance.md)
- [004: Deduplication Logic](./features/004-deduplication-logic.md)
- [005: AI Scripting & Depth](./features/005-ai-scripting-depth.md)
- [006: UI Refinements](./features/006-ui-refinements.md)
- [007: Environment Branching](./features/007-environment-branching.md)

## ⚠️ Platform & Maintenance Caveats (DEFERRED)
- **YouTube Token Expiration:** If the YouTube broadcast stops in 7 days, it is due to the Google Cloud "Testing" status. 
- **The Fix:** Move the OAuth Consent Screen status to "Production" in the Google Cloud Console. 
- **Status:** Tracking only. Pending workflow verification.

