"""
engine/condition_parser.py — Guvenli kural degerlendirici.

eval / exec KESINLIKLE kullanilmaz (guvenli operator modulu). Sadece whitelist
alan + tanimli operator ile karsilastirma. Gecersiz alan/operator -> ValueError.
"""

import operator

# Kabul edilen state alanlari (baskasi ValueError).
ALLOWED_FIELDS = {
    "watch_minutes_today",
    "episodes_completed_today",
    "watch_party_minutes_today",
    "ratings_given_today",
    "watch_minutes_7d",
    "streak_days",
    "genres_watched_today",
}

# Kabul edilen operatorler.
OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


def _split_condition(condition: str):
    """condition -> (field, op_str, value_str). 3 parca degilse ValueError."""
    parts = condition.strip().split()
    if len(parts) != 3:
        raise ValueError(f"Gecersiz kosul formati (3 parca bekleniyor): {condition!r}")
    return parts[0], parts[1], parts[2]


def parse_condition(condition: str, state: dict) -> bool:
    """
    Bir kosulu guvenli sekilde degerlendirir.
    Ornek: parse_condition('watch_minutes_today >= 60', {'watch_minutes_today': 75})
    """
    field, op_str, value_str = _split_condition(condition)

    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Izin verilmeyen alan: {field}")
    if op_str not in OPERATORS:
        raise ValueError(f"Izin verilmeyen operator: {op_str}")

    actual = float(state.get(field, 0))
    target = float(value_str)
    return bool(OPERATORS[op_str](actual, target))


def get_progress(condition: str, state: dict) -> dict:
    """
    Kosula gore ilerleme yuzdesi.
    Doner: {field, current, target, percentage}
    percentage = min(100, round(current/target*100)); target 0 ise 100.
    """
    field, op_str, value_str = _split_condition(condition)

    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Izin verilmeyen alan: {field}")
    if op_str not in OPERATORS:
        raise ValueError(f"Izin verilmeyen operator: {op_str}")

    current = float(state.get(field, 0))
    target = float(value_str)

    if target == 0:
        percentage = 100
    else:
        percentage = min(100, round(current / target * 100))

    return {
        "field": field,
        "current": current,
        "target": target,
        "percentage": percentage,
    }
