# Turkcell Code Night – Gamification System

Production-ready modular gamification engine with atomic writes, validation layer, and deterministic ranking.

---

# System Architecture

The system processes user activity data and produces:

- Challenge awards
- Points ledger updates
- Badge assignments
- Notifications
- Leaderboard rankings

All outputs are written atomically and validated before persistence.

---

# High-Level Flow

1. Load CSV inputs (activity, challenges, etc.)
2. Build per-user engagement state
3. Evaluate challenge conditions
4. Resolve priority conflicts
5. Generate challenge awards
6. Update points ledger
7. Aggregate total points
8. Assign badges
9. Generate notifications
10. Build deterministic leaderboard
11. Validate integrity
12. Atomic write to output directory

---

# Modular Architecture

state_engine/
- Builds user state metrics (daily, 7-day rolling, streak)

logic_engine/
- rule_engine.py → condition evaluation + priority resolution
- badge_engine.py → threshold-based badge assignment
- notification_engine.py → BiP notification creation
- leaderboard_engine.py → deterministic ranking

models/
- ledger.py → append-only points ledger logic

utils/
- file_loader.py → CSV loading & JSON export
- schema_validator.py → schema validation
- integrity_validator.py → cross-file consistency validation

main.py
- Full pipeline orchestrator
- Atomic write implementation
- Validation before promotion

---

# Atomic Write Strategy

The system writes results to a temporary directory first.

Only after integrity validation passes:
- Files are promoted to the final output directory using os.replace()
- Guarantees no partial writes
- Prevents corrupted output states

If validation fails:
- Existing output remains untouched

This mimics production-grade safe-write behavior.

---

# Data Integrity Validation

Before final persistence:

- Award points must match ledger deltas
- Leaderboard totals must match ledger aggregation
- No duplicate badge assignments
- No orphan challenge references

Ensures full consistency across modules.

---

# Deterministic Leaderboard

Ranking rules:

1. Sort by total_points DESC
2. Tie-break by user_id ASC
3. Consecutive ranking (no gaps)

Guarantees reproducible results.

---

# How to Run

```bash
python main.py 2026-02-16

## AI Layer

The system supports two AI modes:

- LLM mode (OpenAI API)
- Deterministic mode (no API required)

If the API fails or quota is exceeded, the system automatically falls back to deterministic reasoning.

This ensures:
- Reproducibility
- Zero randomness
- Production reliability
