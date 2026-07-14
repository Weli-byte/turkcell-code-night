"""
api/main.py — DGE AI-Native Gamification Engine FastAPI uygulamasi.

Calistirma: uvicorn api.main:app --reload --port 8000
Swagger: http://localhost:8000/docs
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.setup import init_db
from api.routers import (
    auth, users, content, watch, challenges,
    leaderboard, badges, pipeline, ingestion,
    ai_explain, ai_stream, events,
)
from api import mcp_server

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # sema + seed (idempotent)
    yield


app = FastAPI(
    title="DGE — AI-Native Gamification Engine",
    version="2.0",
    lifespan=lifespan,
)

# CORS: auth Bearer header ile yapilir (cookie yok) -> allow_credentials=False.
# Wildcard origin + credentials kombinasyonu guvensizdir; credentials kapatildi.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(content.router)
app.include_router(watch.router)
app.include_router(challenges.router)
app.include_router(leaderboard.router)
app.include_router(badges.router)
app.include_router(pipeline.router)
app.include_router(ingestion.router)
app.include_router(ai_explain.router)
app.include_router(ai_stream.router, prefix="/api/ai")
app.include_router(mcp_server.router, prefix="/api/mcp")
app.include_router(events.router, prefix="/api/events")


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "ai-native", "version": "2.0"}


# Frontend statik dosyalari (API rotalarindan SONRA mount edilir)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
