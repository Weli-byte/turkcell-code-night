from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database.setup import init_db
from api.routers import (
    auth, users, content, watch,
    challenges, leaderboard, badges,
    ai_explain, pipeline, ingestion,
)
import os

app = FastAPI(
    title       = "Gamification Engine API",
    description = "Deterministik video platformu oyunlastirma motoru",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_methods     = ["*"],
    allow_headers     = ["*"],
    allow_credentials = True,
)


@app.on_event("startup")
def startup():
    init_db()
    print("Gamification Engine API basladi")
    print("Swagger: http://localhost:8000/docs")


# API route'lari — StaticFiles mount'tan ONCE kayit edilmeli
@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "deterministic"}


app.include_router(auth.router,        prefix="/api/auth")
app.include_router(users.router,       prefix="/api/users")
app.include_router(content.router,     prefix="/api/content")
app.include_router(watch.router,       prefix="/api/watch")
app.include_router(challenges.router,  prefix="/api/challenges")
app.include_router(leaderboard.router, prefix="/api/leaderboard")
app.include_router(badges.router,      prefix="/api/badges")
app.include_router(ai_explain.router,  prefix="/api/ai")
app.include_router(pipeline.router,    prefix="/api/pipeline")
app.include_router(ingestion.router,   prefix="/api/ingestion")

# Frontend static dosyalari — API route'larindan SONRA mount edilmeli
if os.path.exists("frontend") and any(
    f.endswith(".html") for f in os.listdir("frontend")
    if os.path.isfile(os.path.join("frontend", f))
):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
