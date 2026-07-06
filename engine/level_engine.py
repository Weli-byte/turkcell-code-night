"""
Level Engine — Sprint 15.
Toplam puandan deterministik seviye hesaplar. Random yok, ayrı XP para
birimi yok: XP = points_ledger'daki gerçek toplam puan.

Eğri: seviye n'e ulaşmak için gereken toplam puan T(n) = 50·n·(n+1)
  L1=100, L2=300, L3=600, L4=1000, L5=1500, L6=2100, L7=2800, L8=3600…
Artan aralıklar rozet eşikleriyle uyumludur (Bronze 500 ≈ L3, Gold 3000 ≈ L7).
"""

# Seviye aralığı → unvan (konfigürasyon; iş kuralı değil, etiket)
LEVEL_TITLES = [
    (0,  "Çaylak"),
    (3,  "İzleyici"),
    (6,  "Müdavim"),
    (10, "Maratoncu"),
    (15, "Efsane"),
    (20, "Platform Yıldızı"),
]


def threshold(level: int) -> int:
    """Seviye 'level'e ulaşmak için gereken kümülatif toplam puan."""
    if level <= 0:
        return 0
    return 50 * level * (level + 1)


def title_for(level: int) -> str:
    result = LEVEL_TITLES[0][1]
    for min_level, name in LEVEL_TITLES:
        if level >= min_level:
            result = name
    return result


def get_level(total_points: int) -> dict:
    """Gerçek toplam puandan seviye durumu. Tamamen deterministik."""
    pts = max(0, int(total_points))

    level = 0
    while threshold(level + 1) <= pts:
        level += 1

    cur_base   = threshold(level)
    next_need  = threshold(level + 1)
    xp_in      = pts - cur_base
    xp_span    = next_need - cur_base
    pct        = round(xp_in / xp_span * 100, 1) if xp_span > 0 else 0.0

    return {
        "level":         level,
        "title":         title_for(level),
        "total_points":  pts,
        "level_floor":   cur_base,
        "next_level_at": next_need,
        "xp_in_level":   xp_in,
        "xp_for_next":   xp_span,
        "xp_needed":     next_need - pts,
        "pct":           pct,
        "next_title":    title_for(level + 1),
    }
