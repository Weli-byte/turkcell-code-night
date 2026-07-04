"""AI explanation endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from gamification_backend.api.deps import CurrentUserDep, SessionDep
from gamification_backend.api.schemas import ExplainRequest, ExplainResponse
from gamification_backend.services.explain import explain_for_user

router = APIRouter(tags=["explain"])


@router.post("/explain")
def explain(
    body: ExplainRequest, session: SessionDep, user: CurrentUserDep
) -> ExplainResponse:
    """Answer a question about the caller's points/rank/badges/rewards.

    The answer is produced deterministically by the engine's explanation
    layer; a configured LLM may only rephrase it.
    """

    response = explain_for_user(session, user=user, question=body.question)
    return ExplainResponse(
        user_id=response.user_id,
        question=response.question,
        answer=response.answer,
        evidence=dict(response.evidence),
    )
