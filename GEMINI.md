# **AI Radio — Echo (Instructional Context)**

## **Technical Specs Index**
For detailed logic of specific features, refer to the modular specifications in the specs/ directory:

### 📖 THE BIBLE
**CRITICAL MANDATE:** You MUST read [./specs/ARCHITECTURE.md](./specs/ARCHITECTURE.md) before starting any task flow. You MUST update it immediately after finishing tests if any structural or behavioral logic has changed.

@./specs/ARCHITECTURE.md
@./specs/SYSTEM.md

## **Project Definitions (Conductor)**
@./conductor/product.md
@./conductor/product-guidelines.md
@./conductor/tech-stack.md

## **Code Style Guides**
@./conductor/code_styleguides/general.md
@./conductor/code_styleguides/python.md
@./conductor/code_styleguides/javascript.md
@./conductor/code_styleguides/html-css.md

## **Feature Index**
@./specs/features/001-hybrid-player.md
@./specs/features/002-neural-art.md
@./specs/features/003-satirical-performance.md
@./specs/features/004-deduplication-logic.md
@./specs/features/005-ai-scripting-depth.md
@./specs/features/006-ui-refinements.md

## **Repository Metadata & Background Data**
@./AGENTS.md

---

<CRITICAL_EXECUTION_GUARDRAILS>
As an autonomous engineering agent making modifications in this repository, you must strictly adhere to the following operational parameters and procedural protocols. These rules override any conflicting implementation habits, styles, or standard practices.

### **🛑 PHASE 1: MANDATORY PRE-FLIGHT EXECUTION PROTOCOL**

Before invoking ANY file-editing tool (e.g., `replace`, `write_file`), you MUST think step-by-step and output a brief, explicit plan containing the following three points:
1. **Target Lines:** Identify the exact file name and specific line numbers you intend to modify.
2. **Surgical Scope:** State why this change is the absolute minimum required to achieve the task.
3. **Isolation Guarantee:** Explicitly confirm that this edit leaves all surrounding functions, variables, and code logic entirely untouched.

Do not combine the plan with the tool execution; print the plan first, then execute.

### **🛡️ PHASE 2: TOOL OPERATIONAL MANDATES**
1. STRICT NO REFACTORING: NEVER refactor, rewrite, or "clean up" existing code.  
2. PRESERVE LOGIC & STRUCTURE: Do not change variable names, function signatures, class structures, or logic flow unless it is the DIRECT cause of a functional bug.  
3. SURGICAL EDITS ONLY: Every change MUST be minimal, targeted, and strictly relevant to the task.  
4. NO "CLEAN CODE" BYPASS: "Clean code" or styling enhancements are NOT valid excuses to touch or alter surrounding code blocks.  
5. NO OVERWRITING: NEVER use the `write_file` tool on an existing file. You are strictly restricted to using granular line-replacement tools (`replace`) to ensure transparent edits.
6. ADDITION-ONLY BIAS: When introducing features, insert them as completely isolated blocks. Do not touch, "harmonize," or beautify adjacent established code.

## 🔴 **VERIFICATION — NON-NEGOTIABLE RULES**

1. After EVERY code change, run `npm run verify` (Lightweight Health Check).
2. For any structural AI/TTS change, run `npm run test:integration` (Heavy Dry-Run).
3. **NEVER modify `verify_system.py` thresholds or remove test cases to make a failing test pass.**
4. If `verify` cannot run (missing deps, no network), say so explicitly — do not silently skip it.
5. **STRICT PROVIDER ISOLATION:** You MUST write new test for each feature and ensure that any testing logic (Set B) never hits Groq or Mistral API endpoints. 

Violation of these phases or attempting to alter code outside the planned target lines will compromise system stability and result in immediate task failure. Re-verify these constraints constantly.

</CRITICAL_EXECUTION_GUARDRAILS>