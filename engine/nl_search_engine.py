"""
Natural Language Search Engine — Sprint 25.
Doğal dil sorgusunu GPT-4o yapılandırılmış filtreye çevirir;
sonuçlar HER ZAMAN gerçek parametreli SQL'den gelir.

Güvenlik zinciri:
- LLM'e katalogdaki GERÇEK tür/tip listeleri verilir; dönen filtre bu
  listelere karşı doğrulanır (uydurulan değer elenir).
- LLM sonuç seçmez, sıralamaz, uydurmaz — sadece dili filtreye çevirir.
- LLM yoksa/başarısızsa: sorgu kelimeleri LIKE aramasına düşer (deterministik).
"""

import json
from database.setup import get_db

VALID_SORTS = {"rating", "watches", "duration_asc", "duration_desc"}


def _catalog_vocab(db) -> tuple[list[str], list[str]]:
    genres = [r["genre"] for r in db.execute(
        "SELECT DISTINCT genre FROM content_catalog ORDER BY genre").fetchall()]
    types = [r["content_type"] for r in db.execute(
        "SELECT DISTINCT content_type FROM content_catalog ORDER BY content_type").fetchall()]
    return genres, types


def _sanitize_filter(raw: dict, genres: list[str], types: list[str]) -> dict:
    """GPT çıktısını whitelist'e karşı doğrula — geçersiz her şey atılır."""
    f: dict = {
        "genres": None, "content_type": None,
        "max_duration": None, "min_duration": None,
        "min_rating": None, "sort": None,
        "unwatched_only": False, "keywords": [],
    }
    if isinstance(raw.get("genres"), list):
        valid = [g for g in raw["genres"]
                 if isinstance(g, str) and g.strip().lower() in genres]
        f["genres"] = [g.strip().lower() for g in valid] or None
    if isinstance(raw.get("content_type"), str) and raw["content_type"].strip().lower() in types:
        f["content_type"] = raw["content_type"].strip().lower()
    for key in ("max_duration", "min_duration"):
        try:
            v = int(raw.get(key))
            if 1 <= v <= 600:
                f[key] = v
        except (TypeError, ValueError):
            pass
    try:
        v = float(raw.get("min_rating"))
        if 1 <= v <= 5:
            f["min_rating"] = v
    except (TypeError, ValueError):
        pass
    if isinstance(raw.get("sort"), str) and raw["sort"] in VALID_SORTS:
        f["sort"] = raw["sort"]
    f["unwatched_only"] = bool(raw.get("unwatched_only"))
    if isinstance(raw.get("keywords"), list):
        f["keywords"] = [str(k).strip()[:30] for k in raw["keywords"]
                         if str(k).strip()][:4]
    return f


def _fallback_filter(query: str) -> dict:
    """LLM'siz deterministik filtre: sorgu kelimeleri LIKE araması olur."""
    words = [w for w in query.strip().split() if len(w) >= 2][:4]
    return {
        "genres": None, "content_type": None,
        "max_duration": None, "min_duration": None,
        "min_rating": None, "sort": None,
        "unwatched_only": False, "keywords": words,
    }


def _filter_summary(f: dict) -> str:
    parts = []
    if f["genres"]:
        parts.append("tür: " + ", ".join(f["genres"]))
    if f["content_type"]:
        parts.append(f"tip: {f['content_type']}")
    if f["max_duration"]:
        parts.append(f"süre ≤ {f['max_duration']} dk")
    if f["min_duration"]:
        parts.append(f"süre ≥ {f['min_duration']} dk")
    if f["min_rating"]:
        parts.append(f"⭐ ≥ {f['min_rating']:g}")
    if f["unwatched_only"]:
        parts.append("izlemediklerim")
    if f["sort"]:
        labels = {"rating": "puana göre", "watches": "izlenmeye göre",
                  "duration_asc": "kısadan uzuna", "duration_desc": "uzundan kısaya"}
        parts.append(labels[f["sort"]])
    if f["keywords"]:
        parts.append("kelime: " + ", ".join(f["keywords"]))
    return " · ".join(parts) if parts else "filtresiz"


def _run_filter_sql(db, f: dict, user_id: str) -> list[dict]:
    """Doğrulanmış filtreyi parametreli SQL'e çevirir — enjeksiyon imkânsız."""
    where: list[str] = ["1=1"]
    args:  list = []

    if f["genres"]:
        marks = ",".join("?" for _ in f["genres"])
        where.append(f"cc.genre IN ({marks})")
        args.extend(f["genres"])
    if f["content_type"]:
        where.append("cc.content_type = ?")
        args.append(f["content_type"])
    if f["max_duration"]:
        where.append("cc.duration_minutes <= ?")
        args.append(f["max_duration"])
    if f["min_duration"]:
        where.append("cc.duration_minutes >= ?")
        args.append(f["min_duration"])
    if f["min_rating"]:
        where.append(
            "(SELECT COALESCE(AVG(rating),0) FROM content_ratings cr "
            "WHERE cr.content_id=cc.id) >= ?")
        args.append(f["min_rating"])
    if f["unwatched_only"]:
        where.append(
            "cc.id NOT IN (SELECT content_id FROM watch_sessions WHERE user_id=?)")
        args.append(user_id)
    for kw in f["keywords"]:
        where.append("(cc.title LIKE ? OR cc.genre LIKE ?)")
        args.extend([f"%{kw}%", f"%{kw}%"])

    order = {
        "rating":        "avg_rating DESC, watches DESC",
        "watches":       "watches DESC, avg_rating DESC",
        "duration_asc":  "cc.duration_minutes ASC",
        "duration_desc": "cc.duration_minutes DESC",
    }.get(f["sort"] or "", "watches DESC, cc.title ASC")

    rows = db.execute(f"""
        SELECT cc.id, cc.title, cc.genre, cc.content_type,
               cc.duration_minutes, cc.thumbnail_color,
               (SELECT COUNT(*) FROM watch_sessions ws
                WHERE ws.content_id=cc.id AND ws.ended_at IS NOT NULL) AS watches,
               (SELECT COALESCE(AVG(rating),0) FROM content_ratings cr
                WHERE cr.content_id=cc.id) AS avg_rating
        FROM content_catalog cc
        WHERE {' AND '.join(where)}
        ORDER BY {order}
        LIMIT 8
    """, args).fetchall()

    return [
        dict(r) | {"avg_rating": round(float(r["avg_rating"]), 1),
                   "watches": int(r["watches"])}
        for r in rows
    ]


def nl_search(query: str, user_id: str) -> dict:
    """Doğal dil sorgusu → GPT-4o filtre çevirisi → gerçek SQL sonuçları."""
    db = get_db()
    genres, types = _catalog_vocab(db)

    from engine.llm_adapter import llm_call, LLM_MODEL
    fltr         = None
    llm_enhanced = False

    llm_raw = llm_call(
        system=(
            "Sen bir arama sorgusu çözümleyicisisin. Türkçe doğal dil video "
            "arama sorgusunu JSON filtreye çevirirsin. SADECE JSON döndür."
        ),
        user=(
            f"GEÇERLİ TÜRLER: {genres}\n"
            f"GEÇERLİ TİPLER: {types}\n\n"
            f"JSON şeması (alan uymuyorsa null bırak):\n"
            f'{{"genres": ["tür", ...] | null, "content_type": "tip" | null, '
            f'"max_duration": dakika | null, "min_duration": dakika | null, '
            f'"min_rating": 1-5 | null, '
            f'"sort": "rating"|"watches"|"duration_asc"|"duration_desc" | null, '
            f'"unwatched_only": true|false, '
            f'"keywords": ["başlıkta aranacak kelime", ...]}}\n\n'
            f"Notlar: 'yarım saat'=30dk, 'bir saat'=60dk; 'yüksek puanlı/iyi' "
            f"= min_rating 4; 'popüler' = sort watches; 'en iyi' = sort rating; "
            f"'izlemediğim' = unwatched_only. Tür adlarını SADECE geçerli "
            f"listeden kullan.\n\n"
            f"Sorgu: {query}\n\nJSON:"
        ),
        max_tokens=220,
        temperature=0.0,
    )
    if llm_raw:
        raw = llm_raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            parsed = json.loads(raw.strip())
            if isinstance(parsed, dict):
                fltr = _sanitize_filter(parsed, genres, types)
                llm_enhanced = True
        except (json.JSONDecodeError, TypeError):
            pass

    if fltr is None:
        fltr = _fallback_filter(query)

    results = _run_filter_sql(db, fltr, user_id)

    # Filtre hiçbir şey bulamadıysa kelime aramasına genişle (gerçek fallback)
    widened = False
    if not results and (fltr["genres"] or fltr["min_rating"] or fltr["keywords"]):
        results = _run_filter_sql(db, _fallback_filter(query), user_id)
        widened = bool(results)

    db.close()

    return {
        "query":          query,
        "filter":         fltr,
        "filter_summary": _filter_summary(fltr),
        "results":        results,
        "widened":        widened,
        "llm_enhanced":   llm_enhanced,
        "model":          LLM_MODEL if llm_enhanced else "keyword",
    }
