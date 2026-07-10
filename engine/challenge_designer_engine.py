"""
Challenge Designer Engine — Sprint 24.
GPT-4o gerçek platform metriklerinden YENİ görev önerileri üretir.

Güvenlik zinciri (LLM asla iş kararı vermez):
1. GPT'ye sadece whitelist alanları + operatörler + gerçek metrikler verilir.
2. Dönen her öneri safe condition parser'dan geçirilir — geçmeyen ELENİR.
3. Öneri sadece ADMİN ONAYINDAN sonra (mevcut create endpoint'iyle) görev olur;
   o endpoint koşulu bir kez daha doğrular.

LLM yoksa fallback öneriler de EZBER DEĞİL: kullanıcıların gerçek son 7 gün
medyan aktivitesinden hesaplanır.
"""

import json
from datetime import datetime, timedelta
from database.setup import get_db
from engine.condition_parser import parse_condition, ALLOWED_FIELDS


def _validate_suggestion(s: dict, existing_conditions: set[str]) -> dict | None:
    """GPT önerisini whitelist parser'dan geçir; geçersizse None."""
    try:
        name      = str(s["name"]).strip()
        condition = str(s["condition"]).strip()
        reward    = int(s["reward_points"])
        priority  = int(s.get("priority", 5))
        rationale = str(s.get("rationale", "")).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if not (2 <= len(name) <= 100) or not (1 <= reward <= 10000):
        return None
    priority = max(1, min(20, priority))
    if condition.replace(" ", "") in existing_conditions:
        return None  # birebir aynı koşul zaten var
    try:
        empty_state = {f: 0 for f in ALLOWED_FIELDS}
        parse_condition(condition, empty_state)  # NO eval — whitelist parser
    except ValueError:
        return None
    return {
        "name": name, "condition": condition, "reward_points": reward,
        "priority": priority, "rationale": rationale, "valid": True,
    }


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2


def _deterministic_suggestions(db, existing_conditions: set[str]) -> list[dict]:
    """LLM'siz fallback — gerçek son 7 gün verisinden hesaplanır, sabit eşik yok."""
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = db.execute("""
        SELECT user_id, activity_date, SUM(watch_minutes) AS m,
               SUM(episodes_completed) AS e, SUM(ratings_given) AS r
        FROM user_activities WHERE activity_date >= ?
        GROUP BY user_id, activity_date
    """, (week_ago,)).fetchall()

    day_minutes  = [float(r["m"]) for r in rows if r["m"] > 0]
    day_episodes = [float(r["e"]) for r in rows if r["e"] > 0]
    any_ratings  = any(r["r"] > 0 for r in rows)

    candidates = []
    med_min = _median(day_minutes)
    if med_min > 0:
        target = max(10, round(med_min * 1.2))
        candidates.append({
            "name": "Tempo Yükselt",
            "condition": f"watch_minutes_today >= {target}",
            "reward_points": max(20, round(target * 1.5)),
            "priority": 6,
            "rationale": (f"Aktif kullanıcıların medyan günlük izlemesi "
                          f"{med_min:.0f} dk — %20 üstü ulaşılabilir hedef."),
        })
    med_eps = _median(day_episodes)
    if med_eps > 0:
        target = max(2, round(med_eps + 1))
        candidates.append({
            "name": "Bölüm Avcısı",
            "condition": f"episodes_completed_today >= {target}",
            "reward_points": 60 * target,
            "priority": 6,
            "rationale": (f"Medyan günlük bölüm {med_eps:.0f} — bir fazlası "
                          f"binge davranışını teşvik eder."),
        })
    if not any_ratings:
        candidates.append({
            "name": "Görüş Bildir",
            "condition": "ratings_given_today >= 1",
            "reward_points": 40,
            "priority": 4,
            "rationale": "Son 7 günde hiç oylama yapılmamış — topluluk "
                         "verisini büyütmek için düşük eşikli görev.",
        })

    out = []
    for cand in candidates:
        v = _validate_suggestion(cand, existing_conditions)
        if v:
            out.append(v)
    return out[:3]


def suggest_challenges() -> dict:
    """Gerçek metrikler + mevcut görevlerle GPT-4o'dan 3 öneri; hepsi doğrulanır."""
    from engine.admin_insights_engine import collect_platform_metrics
    metrics = collect_platform_metrics()

    db = get_db()
    existing = db.execute(
        "SELECT name, condition, reward_points, is_active FROM challenges"
    ).fetchall()
    existing_conditions = {
        r["condition"].replace(" ", "") for r in existing
    }

    from engine.llm_adapter import llm_call, is_llm_available, LLM_MODEL
    suggestions: list[dict] = []
    llm_enhanced = False
    model = "deterministic"

    llm_raw = llm_call(
        system=(
            "Sen bir oyunlaştırma tasarımcısısın. Video platformu için YENİ "
            "günlük görevler önerirsin. SADECE geçerli bir JSON dizisi döndür, "
            "başka hiçbir şey yazma."
        ),
        user=(
            f"KULLANILABİLİR ALANLAR (sadece bunlar): {sorted(ALLOWED_FIELDS)}\n"
            f"OPERATÖRLER: >=, >, <=, <, ==, !=\n"
            f"KOŞUL FORMATI: 'alan operatör sayı' (örn 'watch_minutes_today >= 45')\n\n"
            f"MEVCUT GÖREVLER (bunları tekrarlama):\n"
            + "\n".join(f"- {r['name']}: {r['condition']} ({r['reward_points']}p)"
                        for r in existing) + "\n\n"
            f"GERÇEK PLATFORM METRİKLERİ:\n"
            f"{json.dumps(metrics, ensure_ascii=False, indent=2)}\n\n"
            f"Bu verilere dayanarak TAM 3 yeni görev öner. Metriklerdeki zayıf "
            f"noktaları hedefle (tamamlanmayan görevler çok zorsa kolay varyant, "
            f"kullanılmayan özellikler için teşvik). Her öneri şu JSON alanlarını "
            f"içersin: name (Türkçe, yaratıcı), condition, reward_points "
            f"(zorlukla orantılı, 20-500), priority (1-20), rationale "
            f"(hangi metriğe dayandığını söyle, 1 cümle Türkçe).\n"
            f"SADECE JSON dizisi döndür."
        ),
        max_tokens=600,
        temperature=0.6,
    )

    if llm_raw:
        raw = llm_raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            parsed = json.loads(raw.strip())
            if isinstance(parsed, list):
                for s in parsed[:5]:
                    v = _validate_suggestion(s, existing_conditions)
                    if v:
                        suggestions.append(v)
                        existing_conditions.add(v["condition"].replace(" ", ""))
                if suggestions:
                    llm_enhanced = True
                    model = LLM_MODEL
        except (json.JSONDecodeError, TypeError):
            pass  # deterministik fallback'e düş

    if not suggestions:
        suggestions = _deterministic_suggestions(db, existing_conditions)
        model = LLM_MODEL if (is_llm_available() and llm_raw) else "deterministic"

    db.close()

    return {
        "suggestions":  suggestions[:3],
        "llm_enhanced": llm_enhanced,
        "model":        model,
        "note": "Öneriler güvenli parser'dan geçirildi; görev ancak admin "
                "onayıyla (kaydet butonu) oluşturulur.",
    }
