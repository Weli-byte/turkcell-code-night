"""
engine/vector_store.py — ChromaDB ile semantik arama (local, hackathon).

Embedding'ler engine.embedding_service (OpenAI) ile uretilir; ChromaDB'ye acikca
verilir (varsayilan embedding fonksiyonu kullanilmaz). Rastgelelik yok. id'ler
hashlib ile deterministik uretilir.
"""

import hashlib

import chromadb
from chromadb.config import Settings

from engine import embedding_service

DEFAULT_COLLECTION = "user_history"

_client = None


def get_client():
    """Tekil (module-level) ChromaDB client. Telemetri kapali."""
    global _client
    if _client is None:
        _client = chromadb.Client(Settings(anonymized_telemetry=False))
    return _client


def get_or_create_collection(name: str):
    """Collection'i alir; yoksa olusturur. Embedding disaridan verilecegi icin ef None."""
    return get_client().get_or_create_collection(name=name, embedding_function=None)


def _doc_id(user_id: str, text: str) -> str:
    # Deterministik id: hashlib.md5 (PYTHONHASHSEED bagimsiz, built-in hash kullanilmaz).
    return hashlib.md5(f"{user_id}_{text}".encode("utf-8")).hexdigest()


def index(user_id: str, text: str, metadata: dict = None,
          collection_name: str = DEFAULT_COLLECTION) -> bool:
    """Metni vektorize edip ChromaDB'ye ekler (upsert). Doner: bool."""
    vec = embedding_service.encode(text)
    if vec is None:
        return False
    meta = dict(metadata) if metadata else {}
    meta["user_id"] = user_id
    try:
        col = get_or_create_collection(collection_name)
        col.upsert(
            ids=[_doc_id(user_id, text)],
            embeddings=[vec],
            documents=[text],
            metadatas=[meta],
        )
        return True
    except Exception as e:
        print("[vector_store] index hatasi:", e)
        return False


def index_batch(user_id: str, texts: list, metadatas: list = None,
                collection_name: str = DEFAULT_COLLECTION) -> bool:
    """Toplu indexleme (encode_batch). Doner: bool."""
    if not texts:
        return True
    vecs = embedding_service.encode_batch(texts)
    if not vecs or len(vecs) != len(texts):
        return False
    ids = [_doc_id(user_id, t) for t in texts]
    metas = []
    for i, t in enumerate(texts):
        m = dict(metadatas[i]) if (metadatas and i < len(metadatas) and metadatas[i]) else {}
        m["user_id"] = user_id
        metas.append(m)
    try:
        col = get_or_create_collection(collection_name)
        col.upsert(ids=ids, embeddings=vecs, documents=texts, metadatas=metas)
        return True
    except Exception as e:
        print("[vector_store] index_batch hatasi:", e)
        return False


def search(query: str, user_id: str, n: int = 5,
           collection_name: str = DEFAULT_COLLECTION) -> list:
    """Sorguyu vektorize edip user_id filtreli benzer kayitlari dondurur."""
    vec = embedding_service.encode(query)
    if vec is None:
        return []
    try:
        col = get_or_create_collection(collection_name)
        res = col.query(
            query_embeddings=[vec],
            n_results=n,
            where={"user_id": user_id},
        )
    except Exception as e:
        print("[vector_store] search hatasi:", e)
        return []

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out = []
    for i in range(len(docs)):
        out.append({
            "text": docs[i],
            "metadata": metas[i] if i < len(metas) else {},
            "distance": dists[i] if i < len(dists) else None,
        })
    return out


def search_similar_users(user_id: str, n: int = 5) -> list:
    """Bu kullaniciya profil-embedding benzerligi en yuksek kullanicilar (deterministik)."""
    from database.setup import get_db

    base = embedding_service.encode_user_profile(user_id)
    if base is None:
        return []

    db = get_db()
    try:
        others = [r["id"] for r in db.execute(
            "SELECT id FROM users WHERE id != ? ORDER BY id", (user_id,)
        ).fetchall()]
    finally:
        db.close()

    sims = []
    for uid in others:
        vec = embedding_service.encode_user_profile(uid)
        if vec is None:
            continue
        sims.append({
            "user_id": uid,
            "similarity": embedding_service.cosine_similarity(base, vec),
        })
    sims.sort(key=lambda x: (-x["similarity"], x["user_id"]))
    return sims[:n]


def delete_user_data(user_id: str, collection_name: str = DEFAULT_COLLECTION) -> bool:
    """Kullanicinin tum vector kayitlarini siler. Doner: bool."""
    try:
        col = get_or_create_collection(collection_name)
        col.delete(where={"user_id": user_id})
        return True
    except Exception as e:
        print("[vector_store] delete hatasi:", e)
        return False
