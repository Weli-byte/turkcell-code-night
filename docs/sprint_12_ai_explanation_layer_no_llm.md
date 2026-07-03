# Sprint 12 AI Explanation Layer — LLM Olmadan

## Sprint Goal

Create an explanation engine that answers user questions with deterministic,
rule-based, template-driven explanations in Turkish without an LLM.

## Deliverables

- Intent classifier (`classify_intent`).
- Explanation engine (`explain_user_query`).
- Turkish explanation templates.
- Unit tests for intent classification and explanation responses.
- Sprint documentation.

## Created Files

### [NEW] `src/gamification_engine/ai/templates.py`

Holds Turkish explanation templates for:
- Point status
- Leaderboard position (including rank 1, rank > 1, and not on leaderboard)
- Badge requirements (Bronze, Silver, Gold, next badge)
- Rewards won (current batch and history)
- Rewards not won (suppressed, inactive, condition not met, no state)
- Unknown query fallback

### [NEW] `src/gamification_engine/ai/explanation_engine.py`

Contains:
- `ExplanationIntent` string enum.
- `classify_intent()` function mapping user questions to intents using keyword heuristics.
- `explain_user_query()` function evaluating daily state, ledger entries, badges, leaderboard, challenges, and current batch rewards to produce a deterministic explanation and structured evidence.
- Helper functions to extract challenge IDs, badge types, and expected reward IDs.

### [NEW] `tests/unit/ai/__init__.py`

Test package initializer.

### [NEW] `tests/unit/ai/test_explanation_engine.py`

Unit tests verifying:
- Classification of intents based on various questions.
- Explanation generation and evidence details for all 5 intent types.
- Fallback response for unknown queries.

## Design Decisions

- **Deterministic & Explainable**: No random behavior or LLMs are involved. Every response is generated directly from actual state values and config thresholds, and includes structured evidence.
- **Language**: Responses are provided in Turkish to align with client requirements.
- **Priority Order**: Checked badge intents first to avoid classification clashes (e.g. "sıra" matching leaderboard instead of "sıradaki rozet").

## Definition of Done

- [x] Soru intent sınıflandırma (`classify_intent`) çalışıyor.
- [x] Tüm 5 soru tipi için şablon tabanlı Türkçe cevaplar hazırlandı.
- [x] Kanıt verileri (`evidence`) yapılandırıldı.
- [x] Mypy ve Ruff statik analiz testleri başarıyla tamamlandı.
- [x] Birim testleri tüm senaryoları doğruladı.
