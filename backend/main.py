from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from config import get_settings
from database import initialize_database
from models.model import load_recommender

settings = get_settings()
app = FastAPI(title="Summit-Up API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    try:
        app.state.recommender = load_recommender()
        app.state.recommender_error = None
    except Exception as error:
        app.state.recommender = None
        app.state.recommender_error = str(error)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist = settings.frontend_dist
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/{path:path}")
def spa_fallback(path: str):
    index_file = frontend_dist / "index.html"
    if index_file.exists() and not path.startswith("api/"):
        return FileResponse(index_file)
    return {"detail": "Not found"}
