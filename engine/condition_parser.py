"""
Güvenli condition parser.
eval/exec kullanılmaz — whitelist tabanlı parser.
Format: "field operator value"
Örnek: "watch_minutes_today >= 60"
"""

ALLOWED_FIELDS = {
    "watch_minutes_today",
    "episodes_completed_today",
    "watch_party_minutes_today",
    "ratings_given_today",
    "watch_minutes_7d",
    "streak_days",
    "genres_watched_today",
}

OPERATORS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def parse_condition(condition: str, state: dict) -> bool:
    parts = condition.strip().split()
    if len(parts) != 3:
        raise ValueError(f"Geçersiz format: '{condition}'. "
                         f"Beklenen: 'field operator value'")
    field, op_str, value_str = parts
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"İzin verilmeyen alan: '{field}'. "
                         f"İzin verilenler: {ALLOWED_FIELDS}")
    if op_str not in OPERATORS:
        raise ValueError(f"İzin verilmeyen operatör: '{op_str}'. "
                         f"İzin verilenler: {list(OPERATORS.keys())}")
    try:
        threshold = float(value_str)
    except ValueError:
        raise ValueError(f"Sayısal değer bekleniyordu: '{value_str}'")
    actual = float(state.get(field, 0))
    result = OPERATORS[op_str](actual, threshold)
    return result


def get_progress(condition: str, state: dict) -> dict:
    """Koşul için mevcut ilerlemeyi döndürür."""
    parts = condition.strip().split()
    if len(parts) != 3:
        return {"current": 0, "target": 0, "percentage": 0}
    field, _, value_str = parts
    target = float(value_str)
    current = float(state.get(field, 0))
    percentage = min(100, round((current / target * 100) if target > 0 else 0))
    return {
        "field": field,
        "current": current,
        "target": target,
        "percentage": percentage,
    }
