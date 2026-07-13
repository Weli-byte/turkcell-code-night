"""
engine/embedding_service.py — OpenAI text-embedding-3-small ile vektorlestirme.

API key .env'den gelir. Hata durumunda exception firlatmaz (None / bos doner).
Rastgelelik yok; cosine similarity elde hesaplanir.
"""

import os
import json
import math

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMBEDDING_DIM = 1536


def _client():
    return OpenAI(api_key=OPENAI_API_KEY)


def encode(text: str):
    """Tek metni vektorize eder. Hata -> None. Doner: list[float] (1536)."""
    if not OPENAI_API_KEY:
        return None
    try:
        resp = _client().embeddings.create(model=EMBEDDING_MODEL, input=text)
        return list(resp.data[0].embedding)
    except Exception as e:
        print("[embedding] encode hatasi:", e)
        return None


def encode_batch(texts: list) -> list:
    """Toplu vektorize. Bos liste -> []. Hata -> []. Doner: list[list[float]]."""
    if not texts:
        return []
    if not OPENAI_API_KEY:
        return []
    try:
        resp = _client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
        # OpenAI ayni sirayi korur; yine de index'e gore siralayalim.
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [list(d.embedding) for d in ordered]
    except Exception as e:
        print("[embedding] encode_batch hatasi:", e)
        return []


def encode_user_profile(user_id: str):
    """
    Kullanici profilini (state + hafiza) tek stringe cevirip vektorize eder.
    Doner: list[float] veya None.
    """
    from datetime import datetime
    from engine.state_builder import build_user_state
    from engine import memory_store

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        state = build_user_state(user_id, today)
    except Exception:
        state = {}
    memory = memory_store.get(user_id)

    profile_text = (
        f"Kullanici {user_id}. "
        f"Toplam puan {state.get('total_points', 0)}, "
        f"streak {state.get('streak_days', 0)} gun, "
        f"bugun {state.get('watch_minutes_today', 0)} dakika izleme, "
        f"rozetler {state.get('badges', [])}. "
        f"Hafiza: {json.dumps(memory, ensure_ascii=False)}"
    )
    return encode(profile_text)


def cosine_similarity(vec1: list, vec2: list) -> float:
    """
    Iki vektor arasi cosine benzerligi (elde hesap). 0-1 arasina kirpilir.
    Uzunluklar farkli veya sifir vektor -> 0.0.
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = 0.0
    n1 = 0.0
    n2 = 0.0
    for a, b in zip(vec1, vec2):
        dot += a * b
        n1 += a * a
        n2 += b * b
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = dot / (math.sqrt(n1) * math.sqrt(n2))
    # Spec: 0-1 arasi dondur.
    return max(0.0, min(1.0, cos))
