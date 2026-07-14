"""
api/mcp_server.py — Model Context Protocol (MCP) destegi.

Claude Desktop, Cursor, VS Code uyumlu basit MCP kopru katmani.
Tool cagrilari gercek engine fonksiyonlarina baglanir.

GUVENLIK NOTU (bilincli tradeoff): Plan geregi MCP endpoint'leri auth'suz —
MCP istemcileri (Claude Desktop vb.) bu API'nin JWT'sini tasimaz ve plan
dogrulama testleri header'siz cagirir. Production'da: istemci basina API key
+ user_id scope zorunlu tutulmali.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["mcp"])

MCP_TOOLS = [
    {
        "name": "get_user_state",
        "description": "Kullanicinin gunluk durumunu getirir",
        "parameters": {"user_id": "string"},
    },
    {
        "name": "generate_challenge",
        "description": "Kisisel AI challenge uretir",
        "parameters": {"user_id": "string"},
    },
    {
        "name": "get_leaderboard",
        "description": "Leaderboard listesi getirir",
        "parameters": {"category": "string", "limit": "integer"},
    },
    {
        "name": "explain",
        "description": "AI aciklama uretir",
        "parameters": {"question": "string", "user_id": "string"},
    },
]


class ConnectBody(BaseModel):
    client_name: str
    version: str


class CallBody(BaseModel):
    tool: str
    parameters: dict = {}


@router.post("/connect")
def mcp_connect(body: ConnectBody):
    return {
        "status": "connected",
        "server": "dge-gamification",
        "version": "2.0",
        "client": body.client_name,
        "tools_available": len(MCP_TOOLS),
    }


@router.get("/tools")
def mcp_tools():
    return {"tools": MCP_TOOLS}


@router.post("/call")
def mcp_call(body: CallBody):
    params = body.parameters or {}

    if body.tool == "get_user_state":
        from engine.state_builder import build_user_state
        result = build_user_state(
            params.get("user_id", ""),
            datetime.now().strftime("%Y-%m-%d"),
        )
    elif body.tool == "generate_challenge":
        from engine.ai_challenge_engine import generate_personal_challenges
        result = generate_personal_challenges(params.get("user_id", ""))
    elif body.tool == "get_leaderboard":
        from engine.ai_leaderboard import get_category_leaderboard
        try:
            result = get_category_leaderboard(
                params.get("category", "ai_score"),
                int(params.get("limit", 50)),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif body.tool == "explain":
        from engine.explanation_engine import explain
        result = explain(params.get("question", ""), params.get("user_id", ""))
    else:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen tool: {body.tool}")

    return {
        "tool": body.tool,
        "result": result,
        "executed_at": datetime.now().isoformat(),
    }
