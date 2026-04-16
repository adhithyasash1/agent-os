"""FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router, get_components
from .config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_components()
    logging.getLogger("agentos").info(
        "agentos-core ready — profile=%s backend=%s",
        settings.profile, settings.llm_backend,
    )
    yield


app = FastAPI(title="agentos-core", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


# --- minimal static dashboard at / ---
_ui_dir = Path(__file__).resolve().parent.parent / "ui"
if _ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=_ui_dir), name="ui")


@app.get("/")
async def root():
    index = _ui_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": "agentos-core", "docs": "/docs", "api": settings.api_prefix}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agentos.main:app", host="0.0.0.0", port=8000, reload=False)
