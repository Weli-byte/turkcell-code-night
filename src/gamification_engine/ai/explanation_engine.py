"""Deterministic, rule-based explanation engine for user questions."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from gamification_engine.ai.templates import (
    BADGE_EARNED_TEMPLATE,
    BADGE_REQUIREMENT_TEMPLATE,
    LEADERBOARD_POSITION_RANK_1,
    LEADERBOARD_POSITION_TEMPLATE,
    POINTS_STATUS_TEMPLATE,
    REWARD_NOT_WON_CONDITION_TEMPLATE,
    REWARD_NOT_WON_INACTIVE_TEMPLATE,
    REWARD_NOT_WON_NO_STATE_TEMPLATE,
    REWARD_NOT_WON_SUPPRESSED_TEMPLATE,
    REWARD_WON_TEMPLATE,
    UNKNOWN_QUESTION_TEMPLATE,
)
from gamification_engine.config.badge_config import BADGE_THRESHOLDS
from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.models import (
    BadgeAssignment,
    ChallengeDefinition,
    DailyUserState,
    ExplanationResponse,
    LeaderboardEntry,
    PointsLedgerEntry,
    RewardEvent,
)
from gamification_engine.rules.condition_parser import parse_condition


class ExplanationIntent(StrEnum):
    """Supported explanation intents classified from user queries."""

    POINTS_STATUS = "POINTS_STATUS"
    LEADERBOARD_POSITION = "LEADERBOARD_POSITION"
    BADGE_REQUIREMENT = "BADGE_REQUIREMENT"
    REWARD_WON = "REWARD_WON"
    REWARD_NOT_WON = "REWARD_NOT_WON"
    UNKNOWN = "UNKNOWN"


def classify_intent(question: str) -> ExplanationIntent:
    """Classify user query into one of the supported intents."""

    q = question.lower()

    if any(
        k in q
        for k in [
            "rozet",
            "badge",
            "gold",
            "silver",
            "bronze",
            "altın",
            "gümüş",
            "bronz",
        ]
    ):
        return ExplanationIntent.BADGE_REQUIREMENT

    if any(k in q for k in ["lider", "sıra", "derece", "tablo", "rank", "skor"]):
        return ExplanationIntent.LEADERBOARD_POSITION

    if any(k in q for k in ["neden", "niye", "nasıl"]):
        if any(
            k in q
            for k in ["kazanamadım", "alamadım", "verilmedi", "suppress", "reddet"]
        ):
            return ExplanationIntent.REWARD_NOT_WON
        if any(k in q for k in ["kazandım", "aldım", "verildi", "hak ettim"]):
            return ExplanationIntent.REWARD_WON

    if any(
        k in q for k in ["kazanamadım", "alamadım", "verilmedi", "alamadım"]
    ):
        return ExplanationIntent.REWARD_NOT_WON
    if any(k in q for k in ["kazandım", "aldım", "verildi", "kazandım"]):
        return ExplanationIntent.REWARD_WON

    if any(k in q for k in ["puan", "skor", "score"]):
        return ExplanationIntent.POINTS_STATUS

    return ExplanationIntent.UNKNOWN


def _extract_challenge_id(
    question: str, challenges: list[ChallengeDefinition]
) -> str | None:
    for challenge in challenges:
        if challenge.challenge_id.lower() in question.lower():
            return challenge.challenge_id
    match = re.search(r"(C-\d+|c-\d+|C\d+|c\d+)", question)
    if match:
        return match.group(1).upper()
    return None


def _extract_badge_type(question: str) -> BadgeType | None:
    q = question.lower()
    if "gold" in q or "altın" in q:
        return BadgeType.GOLD
    if "silver" in q or "gümüş" in q:
        return BadgeType.SILVER
    if "bronze" in q or "bronz" in q:
        return BadgeType.BRONZE
    return None


def _build_reward_id(user_id: str, reward_date: date, challenge_id: str) -> str:
    raw_key = f"{user_id}|{reward_date.isoformat()}|{challenge_id}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"reward-{digest}"


def explain_user_query(
    question: str,
    user_id: str,
    state: DailyUserState | None,
    ledger_entries: list[PointsLedgerEntry],
    badges: list[BadgeAssignment],
    leaderboard: list[LeaderboardEntry],
    challenges: list[ChallengeDefinition],
    rewards: Iterable[RewardEvent] = (),
) -> ExplanationResponse:
    """Answer user question deterministically based on context."""

    intent = classify_intent(question)
    evidence: dict[str, Any] = {}
    answer = UNKNOWN_QUESTION_TEMPLATE

    if intent == ExplanationIntent.POINTS_STATUS:
        user_entries = [e for e in ledger_entries if e.user_id == user_id]
        total_points = sum(e.points_delta for e in user_entries)
        answer = POINTS_STATUS_TEMPLATE.format(total_points=total_points)
        evidence = {"total_points": total_points}

    elif intent == ExplanationIntent.LEADERBOARD_POSITION:
        user_entry = next((e for e in leaderboard if e.user_id == user_id), None)
        if user_entry is None:
            user_entries = [e for e in ledger_entries if e.user_id == user_id]
            total_points = sum(e.points_delta for e in user_entries)
            answer = (
                f"Liderlik tablosunda yer almıyorsunuz. Toplam {total_points} "
                "puanınız var. Liderlik tablosuna girmek için en az 1 puan "
                "kazanmalısınız."
            )
            evidence = {"rank": None, "total_points": total_points}
        else:
            rank = user_entry.rank
            total_points = user_entry.total_points
            if rank == 1:
                answer = LEADERBOARD_POSITION_RANK_1.format(
                    total_points=total_points
                )
                evidence = {"rank": 1, "total_points": total_points}
            else:
                above_entry = next(
                    (e for e in leaderboard if e.rank == rank - 1), None
                )
                if above_entry:
                    points_to_next = above_entry.total_points - total_points
                    next_user_id = above_entry.user_id
                    answer = LEADERBOARD_POSITION_TEMPLATE.format(
                        rank=rank,
                        total_points=total_points,
                        next_user_id=next_user_id,
                        points_to_next=points_to_next,
                    )
                    evidence = {
                        "rank": rank,
                        "total_points": total_points,
                        "next_user_id": next_user_id,
                        "points_to_next": points_to_next,
                    }
                else:
                    answer = (
                        f"Liderlik tablosunda {rank}. sıradasınız. "
                        f"Toplam {total_points} puanınız var."
                    )
                    evidence = {"rank": rank, "total_points": total_points}

    elif intent == ExplanationIntent.BADGE_REQUIREMENT:
        user_badges = [b.badge_type for b in badges if b.user_id == user_id]
        target_badge_type = _extract_badge_type(question)

        if target_badge_type is None:
            earned_types = set(user_badges)
            next_threshold = None
            for t in BADGE_THRESHOLDS:
                if t.badge_type not in earned_types:
                    next_threshold = t
                    break
            if next_threshold is None:
                answer = (
                    "Tebrikler! En yüksek rozet olan Gold rozet dahil tüm "
                    "rozetleri kazandınız."
                )
                evidence = {"badge_status": "ALL_EARNED"}
                return ExplanationResponse(user_id, question, answer, evidence)
            target_badge_type = next_threshold.badge_type

        if target_badge_type in user_badges:
            answer = BADGE_EARNED_TEMPLATE.format(
                badge_type=target_badge_type.value
            )
            evidence = {
                "target_badge": target_badge_type.value,
                "status": "ALREADY_EARNED",
            }
        else:
            threshold = next(
                (t for t in BADGE_THRESHOLDS if t.badge_type == target_badge_type),
                None,
            )
            if threshold:
                user_entries = [e for e in ledger_entries if e.user_id == user_id]
                user_points = sum(e.points_delta for e in user_entries)
                required_points = threshold.required_points
                remaining_points = max(0, required_points - user_points)
                answer = BADGE_REQUIREMENT_TEMPLATE.format(
                    target_badge=target_badge_type.value,
                    required_points=required_points,
                    current_points=user_points,
                    remaining_points=remaining_points,
                )
                evidence = {
                    "target_badge": target_badge_type.value,
                    "required_points": required_points,
                    "current_points": user_points,
                    "remaining_points": remaining_points,
                }
            else:
                answer = f"Geçersiz rozet tipi: {target_badge_type.value}"
                evidence = {}

    elif intent == ExplanationIntent.REWARD_WON:
        challenge_id = _extract_challenge_id(question, challenges)
        if challenge_id is None:
            user_ledger = sorted(
                [e for e in ledger_entries if e.user_id == user_id],
                key=lambda e: e.created_at,
                reverse=True,
            )
            if user_ledger:
                entry = user_ledger[0]
                answer = REWARD_WON_TEMPLATE.format(
                    challenge_id=entry.source_ref,
                    reward_date=entry.created_at.date().isoformat(),
                    points=entry.points_delta,
                )
                evidence = {
                    "challenge_id": entry.source_ref,
                    "reward_date": entry.created_at.date().isoformat(),
                    "points": entry.points_delta,
                }
            else:
                answer = "Henüz kazandığınız bir ödül bulunmuyor."
                evidence = {}
        else:
            assert challenge_id is not None
            cid = challenge_id
            reward = next(
                (
                    r
                    for r in rewards
                    if r.user_id == user_id and r.challenge_id == cid
                ),
                None,
            )
            if reward is None:

                def matches_challenge(entry: PointsLedgerEntry) -> bool:
                    reward_date = entry.created_at.date()
                    expected_id = _build_reward_id(
                        user_id, reward_date, cid
                    )
                    return entry.source_ref == expected_id

                matching_entry = next(
                    (
                        e
                        for e in ledger_entries
                        if e.user_id == user_id and matches_challenge(e)
                    ),
                    None,
                )
                if matching_entry:
                    reward_date_str = matching_entry.created_at.date().isoformat()
                    points = matching_entry.points_delta
                    answer = REWARD_WON_TEMPLATE.format(
                        challenge_id=challenge_id,
                        reward_date=reward_date_str,
                        points=points,
                    )
                    evidence = {
                        "challenge_id": challenge_id,
                        "reward_date": reward_date_str,
                        "points": points,
                        "status": "WON",
                    }
                else:
                    answer = f"Challenge {challenge_id} ödülünü kazanmadınız."
                    evidence = {"challenge_id": challenge_id, "status": "NOT_WON"}
            else:
                answer = REWARD_WON_TEMPLATE.format(
                    challenge_id=challenge_id,
                    reward_date=reward.reward_date.isoformat(),
                    points=reward.reward_points,
                )
                evidence = {
                    "challenge_id": challenge_id,
                    "reward_date": reward.reward_date.isoformat(),
                    "points": reward.reward_points,
                    "status": "WON",
                }

    elif intent == ExplanationIntent.REWARD_NOT_WON:
        challenge_id = _extract_challenge_id(question, challenges)
        if challenge_id is None:
            answer = (
                "Neden ödül alamadığınızı öğrenmek için lütfen spesifik bir "
                "challenge belirtin (örn: 'Neden C-01 ödülünü alamadım?')."
            )
            evidence = {}
        else:
            challenge = next(
                (c for c in challenges if c.challenge_id == challenge_id), None
            )
            if challenge is None:
                answer = f"Geçersiz challenge ID: {challenge_id}"
                evidence = {}
            elif not challenge.is_active:
                answer = REWARD_NOT_WON_INACTIVE_TEMPLATE.format(
                    challenge_id=challenge_id
                )
                evidence = {"challenge_id": challenge_id, "active": False}
            else:
                assert challenge_id is not None
                cid = challenge_id
                user_rewards = [r for r in rewards if r.user_id == user_id]
                suppressing_reward = next(
                    (
                        r
                        for r in user_rewards
                        if cid in r.suppressed_challenge_ids
                    ),
                    None,
                )

                if suppressing_reward:
                    answer = REWARD_NOT_WON_SUPPRESSED_TEMPLATE.format(
                        challenge_id=cid,
                        selected_challenge_id=suppressing_reward.challenge_id,
                    )
                    evidence = {
                        "challenge_id": cid,
                        "status": "SUPPRESSED",
                        "suppressed_by": suppressing_reward.challenge_id,
                    }
                else:

                    def matches_challenge(entry: PointsLedgerEntry) -> bool:
                        reward_date = entry.created_at.date()
                        expected_id = _build_reward_id(
                            user_id, reward_date, cid
                        )
                        return entry.source_ref == expected_id

                    has_won = any(
                        e
                        for e in ledger_entries
                        if e.user_id == user_id and matches_challenge(e)
                    )
                    if has_won:
                        answer = (
                            f"Challenge {challenge_id} ödülünü zaten kazandınız."
                        )
                        evidence = {
                            "challenge_id": challenge_id,
                            "status": "WON",
                        }
                    else:
                        if state is None:
                            answer = REWARD_NOT_WON_NO_STATE_TEMPLATE.format(
                                challenge_id=challenge_id
                            )
                            evidence = {
                                "challenge_id": challenge_id,
                                "status": "NO_STATE",
                            }
                        else:
                            rule_context = state.to_rule_context()
                            try:
                                parsed_cond = parse_condition(
                                    challenge.condition,
                                    allowed_fields=set(rule_context),
                                )
                                left_val = rule_context[parsed_cond.field_name]
                                right_val = parsed_cond.literal_value
                                state_values = (
                                    f"{parsed_cond.field_name} = {left_val}"
                                )

                                answer = (
                                    REWARD_NOT_WON_CONDITION_TEMPLATE.format(
                                        challenge_id=challenge_id,
                                        condition=challenge.condition,
                                        state_values=state_values,
                                    )
                                )
                                evidence = {
                                    "challenge_id": challenge_id,
                                    "status": "CONDITION_FAILED",
                                    "condition": challenge.condition,
                                    "field_name": parsed_cond.field_name,
                                    "current_value": left_val,
                                    "required_value": right_val,
                                    "operator": parsed_cond.operator.value,
                                }
                            except Exception as exc:
                                answer = (
                                    f"Challenge {challenge_id} koşulu "
                                    f"({challenge.condition}) değerlendirilirken "
                                    f"hata oluştu: {exc}"
                                )
                                evidence = {"error": str(exc)}

    return ExplanationResponse(
        user_id=user_id,
        question=question,
        answer=answer,
        evidence=evidence,
    )
