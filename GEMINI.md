# AI Radio — Echo (Instructional Context)

## Technical Specs Index
For detailed logic of specific features, refer to the modular specifications in the `specs/` directory:
-   **System Architecture:** [specs/SYSTEM.md](./specs/SYSTEM.md)
-   **Hybrid Media Player:** [specs/features/001-hybrid-player.md](./specs/features/001-hybrid-player.md)
-   **Neural Art Engine:** [specs/features/002-neural-art.md](./specs/features/002-neural-art.md)
-   **Satirical Performance:** [specs/features/003-satirical-performance.md](./specs/features/003-satirical-performance.md)

---

## Repository Metadata & Background Data
@./AGENTS.md

---

<CRITICAL_EXECUTION_GUARDRAILS>
As an autonomous engineering agent making modifications in this repository, you must strictly adhere to the following operational parameters and procedural protocols. These rules override any conflicting implementation habits, styles, or standard practices.

### 🛑 PHASE 1: MANDATORY PRE-FLIGHT EXECUTION PROTOCOL
Before invoking ANY file-editing tool (e.g., `replace`, `write_file`), you MUST think step-by-step and output a brief, explicit plan containing the following three points:
1. **Target Lines:** Identify the exact file name and specific line numbers you intend to modify.
2. **Surgical Scope:** State why this change is the absolute minimum required to achieve the task.
3. **Isolation Guarantee:** Explicitly confirm that this edit leaves all surrounding functions, variables, and code logic entirely untouched.

Do not combine the plan with the tool execution; print the plan first, then execute.

### 🛡️ PHASE 2: TOOL OPERATIONAL MANDATES
1. STRICT NO REFACTORING: NEVER refactor, rewrite, or "clean up" existing code.
2. PRESERVE LOGIC & STRUCTURE: Do not change variable names, function signatures, class structures, or logic flow unless it is the DIRECT cause of a functional bug.
3. SURGICAL EDITS ONLY: Every change MUST be minimal, targeted, and strictly relevant to the task.
4. NO "CLEAN CODE" BYPASS: "Clean code" or styling enhancements are NOT valid excuses to touch or alter surrounding code blocks.
5. NO OVERWRITING: NEVER use the `write_file` tool on an existing file. You are strictly restricted to using granular line-replacement tools (`replace`) to ensure transparent edits.
6. ADDITION-ONLY BIAS: When introducing features, insert them as completely isolated blocks. Do not touch, "harmonize," or beautify adjacent established code.

Violation of these phases or attempting to alter code outside the planned target lines will compromise system stability and result in immediate task failure. Re-verify these constraints constantly.
</CRITICAL_EXECUTION_GUARDRAILS>