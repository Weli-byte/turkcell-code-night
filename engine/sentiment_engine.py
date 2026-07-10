"""
Sentiment Engine — Sprint 26.
Gerçek kullanıcı yorumlarını GPT-4o ile duygu analizi (pozitif/negatif/notr).

Kurallar:
- Her yorum SADECE BİR KEZ analiz edilir; etiket comment_sentiments'a kalıcı
  yazılır (tekrar GPT çağrısı yok).
- Batch analiz: bekleyen yorumlar tek çağrıda numaralı liste olarak gönderilir.
- Çıktı doğrulama: yalnızca {pozitif, negatif, notr} kabul edilir; format
  bozuksa o yorum ETİKETLENMEDEN kalır (sonraki denemede tekrar).
- LLM yoksa UYDURMA ETİKET YOK — kelime listesi ezberi kullanılmaz; yorum
  'analiz edilmemiş' kalır ve UI bunu dürüstçe gösterir.
- Duygu skoru deterministik türevdir: (pozitif - negatif) / analiz_edilen.
"""

from datetime import datetime
from database.setup import get_db

VALID_LABELS = {"pozitif", "negatif", "notr"}


def analyze_pending(content_id: str | None = None, limit: int = 20) -> int:
    """
    Etiketi olmayan yorumları GPT-4o ile toplu analiz eder.
    content_id verilirse sadece o içeriğin bekleyenleri.
    Kaydedilen etiket sayısını döndürür; LLM yoksa 0 (hiçbir şey uydurulmaz).
    """
    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    if not is_llm_available():
        return 0

    db    = get_db()
    query = """
        SELECT cc.id, cc.comment FROM content_comments cc
        LEFT JOIN comment_sentiments cs ON cs.comment_id = cc.id
        WHERE cs.comment_id IS NULL
    """
    args: list = []
    if content_id:
        query += " AND cc.content_id = ?"
        args.append(content_id)
    query += " ORDER BY cc.created_at ASC LIMIT ?"
    args.append(limit)
    pending = db.execute(query, args).fetchall()

    if not pending:
        db.close()
        return 0

    numbered = "\n".join(
        f"{i + 1}. {p['comment'][:300]}" for i, p in enumerate(pending)
    )
    llm_raw = llm_call(
        system=(
            "Sen bir Türkçe duygu analizi sınıflandırıcısısın. Video platformu "
            "yorumlarını sınıflandırırsın. Her satır için SADECE "
            "'numara: pozitif' veya 'numara: negatif' veya 'numara: notr' yaz. "
            "Başka hiçbir şey yazma."
        ),
        user=(
            f"Şu {len(pending)} yorumu sınıflandır:\n{numbered}\n\n"
            f"Çıktı formatı (tam {len(pending)} satır):\n1: etiket\n2: etiket"
        ),
        max_tokens=12 * len(pending) + 20,
        temperature=0.0,
    )

    if not llm_raw:
        db.close()
        return 0

    # Satırları çözümle: "1: pozitif" → index, etiket
    labels: dict[int, str] = {}
    for line in llm_raw.strip().split("\n"):
        line = line.strip().lower().replace("nötr", "notr")
        if ":" not in line:
            continue
        num_part, label_part = line.split(":", 1)
        num_part   = num_part.strip().lstrip("#").rstrip(".")
        label_part = label_part.strip().strip(".")
        try:
            idx = int(num_part)
        except ValueError:
            continue
        if label_part in VALID_LABELS and 1 <= idx <= len(pending):
            labels[idx] = label_part

    now_iso = datetime.now().isoformat()
    saved   = 0
    for i, p in enumerate(pending):
        label = labels.get(i + 1)
        if label:  # doğrulanamayan yorum etiketlenmeden kalır — uydurma yok
            db.execute(
                "INSERT OR IGNORE INTO comment_sentiments "
                "(comment_id, sentiment, model, analyzed_at) VALUES (?, ?, ?, ?)",
                (p["id"], label, LLM_MODEL, now_iso),
            )
            saved += 1
    db.commit()
    db.close()
    return saved


def get_content_sentiment(content_id: str) -> dict:
    """İçeriğin duygu dağılımı — yalnızca gerçekten analiz edilmiş yorumlardan."""
    db   = get_db()
    rows = db.execute("""
        SELECT cs.sentiment, COUNT(*) AS c
        FROM content_comments cc
        JOIN comment_sentiments cs ON cs.comment_id = cc.id
        WHERE cc.content_id = ?
        GROUP BY cs.sentiment
    """, (content_id,)).fetchall()
    total_comments = db.execute(
        "SELECT COUNT(*) AS c FROM content_comments WHERE content_id=?",
        (content_id,),
    ).fetchone()["c"]
    db.close()

    dist = {"pozitif": 0, "negatif": 0, "notr": 0}
    for r in rows:
        dist[r["sentiment"]] = int(r["c"])
    analyzed = sum(dist.values())
    score = round((dist["pozitif"] - dist["negatif"]) / analyzed * 100) if analyzed else None

    return {
        "distribution": dist,
        "analyzed":     analyzed,
        "total":        int(total_comments),
        "score":        score,  # -100..100, deterministik türev; analiz yoksa None
    }


def get_platform_sentiment() -> dict:
    """Platform geneli duygu dağılımı (admin insights için)."""
    db   = get_db()
    rows = db.execute(
        "SELECT sentiment, COUNT(*) AS c FROM comment_sentiments GROUP BY sentiment"
    ).fetchall()
    db.close()
    dist = {"pozitif": 0, "negatif": 0, "notr": 0}
    for r in rows:
        dist[r["sentiment"]] = int(r["c"])
    analyzed = sum(dist.values())
    return {
        "distribution": dist,
        "analyzed":     analyzed,
        "score": round((dist["pozitif"] - dist["negatif"]) / analyzed * 100) if analyzed else None,
    }
