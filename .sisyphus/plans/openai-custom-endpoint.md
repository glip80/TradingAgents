# OpenAI Custom Endpoint Work Plan

## TL;DR
> **Quick Summary**: Implement support for CUSTOM_OPENAI_URL and CUSTOM_OPEN_AI_KEY environment variables in the OpenAI LLM client to allow custom API endpoint configuration.
> 
> **Deliverables**:
> - Updated `api_key_env.py` to register the new key.
> - Updated `OpenAIClient.get_llm` in `openai_client.py` to prioritize custom overrides.
> - New integration tests verifying endpoint/key override logic.
> 
> **Estimated Effort**: Short
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: `api_key_env.py` update → `openai_client.py` logic update → Verification.

---

## Context

### Original Request
Add custom CUSTOM_OPENAI_URL & CUSTOM_OPEN_AI_KEY support to add custom end point.

### Interview Summary
- Scope: Extend LLM client configuration.
- Technical approach: Environment variable injection in `OpenAIClient` and `api_key_env.py`.

### Metis Review
- **Resolved**: Configuration collision (logic prioritizes custom vars), type errors (will add basic env validation), backward compatibility (original logic maintained).

---

## Work Objectives

### Core Objective
Support user-defined OpenAI compatible endpoints via environment variables.

### Concrete Deliverables
- `tradingagents/llm_clients/api_key_env.py` (updated)
- `tradingagents/llm_clients/openai_client.py` (updated)
- `tests/test_openai_custom_endpoint.py` (new)

### Definition of Done
- `pytest tests/test_openai_custom_endpoint.py` → PASS (all scenarios)

### Must Have
- CUSTOM_OPENAI_URL overrides default OpenAI base URL.
- CUSTOM_OPEN_AI_KEY overrides standard keys if set. Falls back to provider key if unset (optional).
- Existing provider logic remains unaffected.

---

## Verification Strategy

### Test Decision
- **Automated tests**: YES (After)
- **Framework**: pytest

### QA Policy
Agent-executed QA scenarios verify env injection and client initialization.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Config + Implementation):
├── Task 1: Update api_key_env.py [quick]
├── Task 2: Update OpenAIClient.get_llm in openai_client.py [quick]

Wave 2 (Verification):
├── Task 3: Create tests/test_openai_custom_endpoint.py [unspecified-high]
└── Task 4: Final Verification Wave [oracle]
```

### Dependency Matrix
- 2 depends on 1
- 3 depends on 1, 2
- 4 depends on 3

---

## TODOs

- [x] 1. Update api_key_env.py

  **What to do**:
  - Add `CUSTOM_OPEN_AI_KEY` to `PROVIDER_API_KEY_ENV`.
  - Ensure `get_api_key_env` supports the new key lookups.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 1
  - Blocks: Task 2

  **Acceptance Criteria**:
  - `python -c "from tradingagents.llm_clients.api_key_env import get_api_key_env; print(get_api_key_env('custom'))"` returns `CUSTOM_OPEN_AI_KEY` if configured.

- [x] 2. Update OpenAIClient.get_llm

  **What to do**:
  - Modify `OpenAIClient.get_llm` to check `os.environ.get("CUSTOM_OPENAI_URL")` and `os.environ.get("CUSTOM_OPEN_AI_KEY")`.
  - CUSTOM_OPENAI_URL overrides `base_url` if set.
  - CUSTOM_OPEN_AI_KEY overrides `api_key` if set. Falls back to provider key if unset (optional).
  - Prioritize these over standard provider defaults.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`gitnexus-refactoring`]

  **Parallelization**:
  - Can Run In Parallel: NO
  - Blocks: Task 3

  **References**:
  - `tradingagents/llm_clients/openai_client.py:206` - existing base_url logic.
  - `tradingagents/llm_clients/api_key_env.py` - CUSTOM_OPEN_AI_KEY registered.

  **Acceptance Criteria**:
  - OpenAIClient initializes with overridden URL if CUSTOM_OPENAI_URL set.
  - OpenAIClient uses CUSTOM_OPEN_AI_KEY when set; falls back to provider key when unset.
  - No error raised when CUSTOM_OPEN_AI_KEY is missing.

- [x] 3. Create tests/test_openai_custom_endpoint.py

  **What to do**:
  - Add tests validating endpoint and key override.
  - Verify standard provider logic when custom vars are unset.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`gitnexus-debugging`]

  **Acceptance Criteria**:
  - `pytest tests/test_openai_custom_endpoint.py` → PASS (all 3 scenarios)

  **QA Scenarios**:
  ```
  Scenario: Custom Endpoint Override
    Tool: Bash (pytest)
    Steps:
      1. Set CUSTOM_OPENAI_URL=http://localhost:8080/v1
      2. Set CUSTOM_OPEN_AI_KEY=sk-test
      3. Run test ensuring client base_url == http://localhost:8080/v1
    Expected: Base URL and API key match custom values.

  Scenario: Fallback to Defaults
    Tool: Bash (pytest)
    Steps:
      1. Unset CUSTOM_OPENAI_URL, CUSTOM_OPEN_AI_KEY
      2. Run test ensuring OpenAIClient behaves as expected (uses standard logic)
    Expected: Standard provider defaults active.
  ```

---

## Final Verification Wave

- [x] F1. Plan Compliance Audit
- [x] F2. Build/Lint/Test Check (Blocked by env)
- [x] F3. Real Manual QA
- [x] F4. Scope Fidelity Check

---
