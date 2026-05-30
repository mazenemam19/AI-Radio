# Spec-Driven Development (SDD) Skill

This skill enforces a rigid, plan-first workflow for the AI Radio — Echo project. It is designed to prevent structural drift, eliminate unnecessary refactoring, and ensure absolute stability during feature development.

## 🎯 Purpose
To move from "Vibe Coding" to "Protocol Coding" by establishing a technical contract before any code is modified.

## 🛠️ Activation
This skill is triggered when the user requests a new feature, a complex bug fix, or any structural change to the Echo pipeline.

---

## 📋 The 4-Phase Protocol

### Phase I: Research (Read-Only)
-   **Action:** Use `grep_search`, `glob`, and `read_file` to map the current logic.
-   **Goal:** Identify exactly which lines and variables will be affected.
-   **Constraint:** DO NOT propose changes during this phase.

### Phase II: Spec/Plan (Design)
-   **Action:** Call `enter_plan_mode`.
-   **Artifact:** Create an **Implementation Plan** or `SPEC.md`.
-   **Goal:** Define the *what* and *how* without writing implementation code.
-   **Mandate:** Explicitly state that **No Refactoring** will occur. Every change must be a surgical addition or a logic fix.
-   **Consent:** Wait for the user to review (Ctrl+X) and approve the plan.

### Phase III: Execution (Surgical Act)
-   **Action:** Call `exit_plan_mode`.
-   **Tool:** Use the `replace` tool exclusively for existing files. **NEVER** use `write_file` on existing code.
-   **Goal:** Apply minimal, targeted changes. Do not "harmonize" or "beautify" surrounding code.

### Phase IV: Validation (Verification)
-   **Action:** Run `npm run verify`.
-   **Goal:** Confirm behavioral correctness and ensure no regressions.

---

## ⚖️ High-Priority Constraints
1.  **Strict No-Refactor:** If a variable name or structure is already working, it stays. 
2.  **Persona Preservation:** Every script change must respect the **Echo & Glitch** dynamic (Intellectual vs. Chaotic, naming each other, rhythmic punctuation).
3.  **Resource Safety:** Maintain the **Quota-Saver** strategy.
    *   **Strict Provider Isolation:** Local/Testing code paths MUST NOT overlap with Production providers. 
    *   Set B (Testing) must never hit Groq or Mistral APIs. Uses **Gemini 3.5 Flash / 3.1 Flash-Lite**.
    *   Set A (Production) uses premium engines (70B, Orpheus).
4.  **Token Efficiency:** Avoid high-volume rewrites. Surgical edits save context and tokens.

---

## 🎭 Satirical Excellence
When generating scripts under this skill, adhere to the **Jon Stewart / Stephen Colbert** standard:
-   **Conflict:** Echo and Glitch must argue or disagree.
-   **Specificity:** Name the absurdity. No vague fillers.
-   **Rhythm:** Use `...` and `ALL CAPS` to steer the voice engine.
-   **Pillars:** Respect the Mono-Topic Deep Dive and Threshold-2 Deduplication rules.
