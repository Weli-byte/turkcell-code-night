# Sprint 14 AI Explanation Layer — LLM ile (İsteğe Bağlı Katman)

## Sprint Goal

Introduce an optional, configure-by-environment LLM layer that can rephrase the
deterministic kural motoru explanations to make them friendlier and more natural
to the user, while strictly preserving evidence dates, numbers, and facts.

## Deliverables

- `llm_client.py` using standard library HTTP requests to support both Google Gemini and OpenAI REST APIs.
- Configuration for API timeouts (default 5.0 seconds).
- Robust fallback mechanics returning `None` if keys are missing or calls fail.
- Integration inside CLI `explain` command.
- Unit tests verifying mock API calls and error fallback.
- Sprint documentation.

## Created/Modified Files

### [NEW] `src/gamification_engine/ai/llm_client.py`

HTTP client utilizing `urllib.request`. Reads:
- `GEMINI_API_KEY` to query Gemini API (`gemini-2.5-flash`).
- `OPENAI_API_KEY` to query OpenAI API (`gpt-4o-mini`).

Includes a strict `SYSTEM_PROMPT` instructing the LLM never to alter dates, points, or decisions.

### [MODIFY] `src/gamification_engine/cli/main.py`

Updates `_handle_explain` to call `generate_llm_explanation` and transparently
wrap/inject the LLM rephrased answer if one is successfully generated.

### [NEW] `tests/unit/ai/test_llm_client.py`

Unit tests verifying:
- Successful Gemini response parsing.
- Successful OpenAI response parsing.
- Immediate `None` fallback when no environment keys are present.
- Gracious `None` fallback on network timeout or connection errors.
- Gracious `None` fallback on corrupted JSON responses.

### [NEW] `docs/sprint_14_optional_llm_layer.md`

Documentation of LLM system role rules, prompts, and fail-safe designs.

## Definition of Done

- [x] LLM client can query both Gemini and OpenAI APIs without extra pip dependencies.
- [x] Fail-safe fallback mechanics return rule-based outputs on any error.
- [x] Strict prompt guarantees facts are not modified.
- [x] Unit tests cover all key presence, success, and error paths.
- [x] Type check and Ruff validations are fully green.
