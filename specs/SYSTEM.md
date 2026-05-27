# System Specification: AI Radio — Echo

This is the baseline "contract" for the Echo platform. It defines the foundational logic that all features must inherit.

## 🏗️ Core Architecture
- **Broadcast Pattern:** Mono-Topic Deep Dive (~10 minutes).
- **Client Logic:** Multi-environment aware (Local, Staging, Production).
- **Database:** Polyglot persistence (Supabase for Cloud, SQLite for Local).

## 🛡️ Global Constraints
- **Deduplication:** Keyword Overlap (Threshold: 2) against the last 20 episodes.
- **Quota-Saver:** High-performance Cloud TTS (Groq) is restricted to Production environment only.
- **Duo Persona:** Every broadcast features **Echo** and **Glitch** with established intellectual vs. chaotic dynamics.

## 🔗 Feature Index
Current active modules documented in `specs/features/`:
- [001: Hybrid Media Player](./features/001-hybrid-player.md)
- [002: Neural Art Engine](./features/002-neural-art.md)
- [003: Satirical Performance logic](./features/003-satirical-performance.md)

## ⚠️ Platform & Maintenance Caveats (DEFERRED)
- **YouTube Token Expiration:** If the YouTube broadcast stops in 7 days, it is due to the Google Cloud "Testing" status. 
- **The Fix:** Move the OAuth Consent Screen status to "Production" in the Google Cloud Console. 
- **Status:** Tracking only. Pending workflow verification.

