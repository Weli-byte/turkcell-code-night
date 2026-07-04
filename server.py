"""Development server bridging the landing page UI and the gamification engine.

Serves the static landing page (index.html) from the repository root and
exposes the deterministic engine outputs over a small JSON API:

    GET /                 -> index.html (static files)
    GET /api/summary      -> data/output/run_summary.json
    GET /api/leaderboard  -> data/output/leaderboard.json
    GET /api/badges       -> data/output/badges.json
    GET /api/explain?user_id=u001&question=... -> deterministic explanation
                             (optionally rephrased by the LLM adapter)

The API only reads existing pipeline outputs; it never mutates state.
Run the batch pipeline first (see README) to populate data/output.

Usage:
    python server.py [port]   # default port: 8000
"""

from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from gamification_engine.ai.explanation_engine import (  # noqa: E402
    explain_user_query,
)
from gamification_engine.ai.llm_adapter import (  # noqa: E402
    create_llm_adapter_from_env,
)
from gamification_engine.badges.badge_repository import (  # noqa: E402
    load_badge_assignments_json,
)
from gamification_engine.cli.main import (  # noqa: E402
    _load_leaderboard_json,
    _load_rewards_json,
    _load_states_json,
)
from gamification_engine.ingestion.csv_loader import (  # noqa: E402
    load_challenge_definitions_csv,
)
from gamification_engine.ledger.ledger_repository import (  # noqa: E402
    load_points_ledger_json,
)

OUTPUT_DIR = ROOT / "data" / "output"
CHALLENGES_CSV = ROOT / "data" / "input" / "challenges.csv"


def _read_json(name: str, default: Any) -> Any:
    """Read a pipeline output file, returning a default when missing."""

    path = OUTPUT_DIR / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _explain(user_id: str, question: str) -> dict[str, Any]:
    """Answer a user question using the deterministic explanation engine."""

    states = _load_states_json(OUTPUT_DIR / "states.json")
    ledger = load_points_ledger_json(OUTPUT_DIR / "ledger.json")
    badges = load_badge_assignments_json(OUTPUT_DIR / "badges.json")
    leaderboard = _load_leaderboard_json(OUTPUT_DIR / "leaderboard.json")
    rewards = _load_rewards_json(OUTPUT_DIR / "rewards.json")
    challenges = load_challenge_definitions_csv(CHALLENGES_CSV)

    user_state = next((s for s in states if s.user_id == user_id), None)

    response = explain_user_query(
        question=question,
        user_id=user_id,
        state=user_state,
        ledger_entries=ledger,
        badges=badges,
        leaderboard=leaderboard,
        challenges=challenges,
        rewards=rewards,
    )
    # Optional LLM rephrasing; falls back to the deterministic answer.
    return create_llm_adapter_from_env().enhance(response).to_dict()


class UIBridgeHandler(SimpleHTTPRequestHandler):
    """Static file handler with a JSON API for the engine outputs."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed.path, parse_qs(parsed.query))
            return
        super().do_GET()

    def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if path == "/api/summary":
                payload: Any = _read_json("run_summary.json", {})
            elif path == "/api/leaderboard":
                payload = _read_json("leaderboard.json", [])
            elif path == "/api/badges":
                payload = _read_json("badges.json", [])
            elif path == "/api/explain":
                user_id = (query.get("user_id") or [""])[0].strip()
                question = (query.get("question") or [""])[0].strip()
                if not user_id or not question:
                    self._send_json(
                        {"error": "user_id ve question parametreleri zorunlu."},
                        status=400,
                    )
                    return
                payload = _explain(user_id, question)
            else:
                self._send_json({"error": "Bilinmeyen endpoint."}, status=404)
                return
            self._send_json(payload, status=200)
        except Exception as exc:  # API asla ham traceback döndürmez.
            self._send_json({"error": str(exc)}, status=500)

    def _send_json(self, payload: Any, status: int) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    """Start the UI + API dev server."""

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), UIBridgeHandler)
    print(f"UI + API hazir: http://localhost:{port}")
    print("Durdurmak icin: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
