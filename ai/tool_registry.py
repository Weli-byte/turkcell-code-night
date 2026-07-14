"""
ai/tool_registry.py — AI Tool Registry.

AI'in kullanabildigi araclarin merkezi kaydi. Her tool: ad, aciklama, sprint,
gercek callable. Liste sabit metin degil — callable'lar gercek engine
fonksiyonlarina baglanir ve call_tool ile calistirilabilir.
"""


def _user_state(user_id: str):
    from datetime import datetime
    from engine.state_builder import build_user_state
    return build_user_state(user_id, datetime.now().strftime("%Y-%m-%d"))


def _challenge_generate(user_id: str):
    from engine.ai_challenge_engine import generate_personal_challenges
    return generate_personal_challenges(user_id)


def _badge_progress(user_id: str):
    from engine.badge_engine import get_badge_progress
    from engine.ledger import get_total_points
    return get_badge_progress(user_id, get_total_points(user_id))


def _leaderboard(category: str = "ai_score", limit: int = 50):
    from engine.ai_leaderboard import get_category_leaderboard
    return get_category_leaderboard(category, limit)


def _memory_read(user_id: str):
    from engine import memory_store
    return memory_store.get(user_id)


def _memory_write(user_id: str, key: str, value):
    from engine import memory_store
    return memory_store.update(user_id, key, value)


def _vector_search(query: str, user_id: str, n: int = 5):
    from engine import vector_store
    return vector_store.search(query, user_id, n=n)


def _recommend(user_id: str, rec_type: str = "video", n: int = 5):
    from engine.recommendation_engine import recommend
    return recommend(user_id, rec_type, n)


def _explain(question: str, user_id: str):
    from engine.explanation_engine import explain
    return explain(question, user_id)


# name -> {description, sprint, callable}
_REGISTRY = {
    "get_user_state": {
        "description": "Kullanicinin gunluk durumunu DB'den hesaplar",
        "sprint": "Sprint 1",
        "callable": _user_state,
    },
    "challenge_engine": {
        "description": "AI kisisel challenge uretimi (grounding'li)",
        "sprint": "Sprint 1",
        "callable": _challenge_generate,
    },
    "badge_engine": {
        "description": "Rozet ilerlemesi ve atama bilgisi",
        "sprint": "Sprint 1",
        "callable": _badge_progress,
    },
    "leaderboard_engine": {
        "description": "Coklu kategori deterministik leaderboard",
        "sprint": "Sprint 1",
        "callable": _leaderboard,
    },
    "memory_read": {
        "description": "Kullanici AI hafizasindan okuma",
        "sprint": "Sprint 2",
        "callable": _memory_read,
    },
    "memory_write": {
        "description": "Kullanici AI hafizasina yazma",
        "sprint": "Sprint 2",
        "callable": _memory_write,
    },
    "vector_search": {
        "description": "ChromaDB semantik arama (RAG)",
        "sprint": "Sprint 2",
        "callable": _vector_search,
    },
    "recommendation": {
        "description": "Kisisel oneri uretimi (video/challenge/badge)",
        "sprint": "Sprint 4",
        "callable": _recommend,
    },
    "explain": {
        "description": "Grounded AI aciklama (LLM intent + evidence)",
        "sprint": "Sprint 1",
        "callable": _explain,
    },
}


def list_tools() -> list:
    """Kayitli tum tool'larin metadata listesi."""
    return [
        {"name": name, "description": meta["description"], "sprint": meta["sprint"]}
        for name, meta in _REGISTRY.items()
    ]


def has_tool(name: str) -> bool:
    return name in _REGISTRY


def call_tool(name: str, **kwargs):
    """Kayitli bir tool'u calistirir. Bilinmeyen tool -> KeyError."""
    if name not in _REGISTRY:
        raise KeyError(f"Bilinmeyen tool: {name}")
    return _REGISTRY[name]["callable"](**kwargs)
