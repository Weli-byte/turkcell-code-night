"""FastAPI service layer wrapping the deterministic gamification engine.

The engine package (``gamification_engine``) stays a pure, deterministic
business-logic core. This package adds the live system around it: database
persistence, HTTP API, authentication, live challenge evaluation and the
end-of-day batch. See ``docs/v2_plan.md``.
"""
