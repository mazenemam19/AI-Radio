---
name: model-tier-manager
description: Multi-tier fallback logic for AI engines. Orchestrates Llama 3.3 70B, Gemini 1.5 Flash, and Llama 3.1 8B in a quota-aware queue. Use when implementing resilient AI pipelines that must fail-fast or fallback between free and premium tiers.
---

# Model Tier Manager

This skill governs the "Brain" of the AI Radio Echo suite. It ensures that the system always uses the best available model while strictly protecting quotas and preventing "zombie broadcasts."

## 🏗️ The Tiered Queue

| Tier | Model | Context | Purpose | Quota Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Premium)** | `llama-3.3-70b-versatile` | Full (15 News / 20 Mem) | Production Deep Dive | High (100k daily) |
| **Tier 2 (Reliable)** | `gemini-3.5-flash` | Full (15 News / 20 Mem) | Production Fallback | Low (Massive Free) |
| **Tier 3 (Budget)** | `llama-3.1-8b-instant` | Trimmed (3 News / 1 Mem) | Local / Emergency | High RPM / low TPM |

## ⚖️ Operational Rules

### 1. Intent-Based Routing
- **`is_real_run == True`**: Start at Tier 1. Fallback to Tier 2 on failure/low-quality.
- **`is_real_run == False`**: **ONLY** Tier 2 (Flash) is allowed. Never hit Groq.

### 2. Failure Path (Fail-Fast)
- If a model returns a script that fails the `_is_sufficient` check (brevity, word count), it is considered a **failure**.
- Retries must **decrease context noise**. If Tier 1 fails with 15 news items, Tier 2 should try with 8 news items to prevent the "summary trap."
- If the entire queue fails, return `None`. **NO EMERGENCY PLACEHOLDERS.**

### 3. Quality Gates
- **Production:** 12+ segments, ~150 words/segment.
- **Local:** 10+ segments, ~60 words/segment.

## 📋 Implementation Checklist
- [ ] Implement `ModelTierManager` class in `ai_client.py`.
- [ ] Pass `is_real_run` as the primary routing flag.
- [ ] Ensure `test:integration` strictly uses Tier 2.
- [ ] Update `main.py` to handle `None` and exit code 1.
