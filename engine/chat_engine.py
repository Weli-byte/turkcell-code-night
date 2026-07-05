"""
Chat Engine — Sprint 14.
Konuşma hafızalı AI koç.

Akış:
1. Soru için deterministik evidence üretilir (explanation_engine — gerçek DB).
2. Son N mesaj DB'den okunur (gerçek konuşma geçmişi, simülasyon yok).
3. GPT-4o'ya: sistem kuralları + güncel evidence + geçmiş + yeni soru.
4. Hem soru hem cevap chat_messages'a kaydedilir.
5. LLM yoksa deterministik cevap döner — sistem çalışmaya devam eder.

LLM asla iş kararı vermez: puan/rozet/sıra sayıları evidence'tan gelir.
"""

import json
from datetime import datetime
from database.setup import get_db
from engine.explanation_engine import detect_intent, build_answer, INTENTS

HISTORY_LIMIT = 10  # GPT'ye gönderilen geçmiş mesaj sayısı

CHAT_SYSTEM_PROMPT = """Sen bir video platformu oyunlaştırma koçusun.
Kullanıcıyla çok turlu sohbet ediyorsun; önceki mesajları hatırlar,
bağlama uygun cevap verirsin.

KESİN KURALLAR:
1. Sana her turda 'GÜNCEL VERİLER' bloğu verilir — sayıları SADECE oradan al
2. Sayı uydurma, geçmiş mesajlardaki eski sayılar güncel olmayabilir;
   çelişki varsa GÜNCEL VERİLER geçerlidir
3. Maksimum 4 cümle, samimi ve motive edici Türkçe
4. Puan/rozet/sıra kararlarını sen vermezsin, sadece açıklarsın"""


def _load_history(db, user_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    rows = db.execute(
        "SELECT role, content FROM chat_messages "
        "WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _save_message(db, user_id: str, role: str, content: str,
                  intent: str | None = None, model: str | None = None) -> None:
    db.execute(
        "INSERT INTO chat_messages (user_id, role, content, intent, model, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, role, content, intent, model, datetime.now().isoformat()),
    )


def chat(user_id: str, question: str) -> dict:
    """Çok turlu AI koç sohbeti. Evidence deterministik, dil GPT-4o."""
    # 1) Intent + deterministik cevap/evidence (gerçek DB verisi)
    intent        = detect_intent(question)
    intent_source = "keyword"
    if intent == "general":
        from engine.llm_adapter import classify_intent_llm
        llm_intent = classify_intent_llm(question, INTENTS)
        if llm_intent:
            intent        = llm_intent
            intent_source = "llm"

    det = build_answer(intent, user_id)

    # 2) Konuşma geçmişi (gerçek, DB'den)
    db      = get_db()
    history = _load_history(db, user_id)

    # 3) GPT-4o — güncel evidence her turda yeniden verilir
    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    user_msg = (
        f"GÜNCEL VERİLER (deterministik motor çıktısı):\n"
        f"{json.dumps(det['evidence'], ensure_ascii=False, indent=2)}\n\n"
        f"Motor analizi: {det['answer']}\n\n"
        f"Kullanıcının yeni mesajı: {question}"
    )
    llm_answer = llm_call(
        system=CHAT_SYSTEM_PROMPT,
        user=user_msg,
        history=history,
        max_tokens=350,
    )

    if llm_answer:
        answer, llm_enhanced = llm_answer, True
        model = LLM_MODEL
    else:
        answer, llm_enhanced = det["answer"], False
        model = LLM_MODEL if is_llm_available() else "template"

    # 4) Konuşmayı kaydet (soru + cevap)
    _save_message(db, user_id, "user", question, intent=intent)
    _save_message(db, user_id, "assistant", answer, intent=intent, model=model)
    db.commit()

    count = db.execute(
        "SELECT COUNT(*) AS cnt FROM chat_messages WHERE user_id=?", (user_id,)
    ).fetchone()
    db.close()

    return {
        "answer":        answer,
        "intent":        intent,
        "intent_source": intent_source,
        "evidence":      det["evidence"],
        "llm_enhanced":  llm_enhanced,
        "model":         model,
        "history_used":  len(history),
        "total_messages": int(count["cnt"]),
    }


def get_chat_history(user_id: str, limit: int = 50) -> dict:
    db   = get_db()
    rows = db.execute(
        "SELECT id, role, content, intent, model, created_at "
        "FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    db.close()
    return {"messages": [dict(r) for r in reversed(rows)]}


def clear_chat_history(user_id: str) -> dict:
    db  = get_db()
    cnt = db.execute(
        "SELECT COUNT(*) AS cnt FROM chat_messages WHERE user_id=?", (user_id,)
    ).fetchone()
    db.execute("DELETE FROM chat_messages WHERE user_id=?", (user_id,))
    db.commit()
    db.close()
    return {"ok": True, "deleted": int(cnt["cnt"])}
