"""FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import api_router, build_components
from .config import settings

import os
from fastapi.staticfiles import StaticFiles

os.makedirs("data/exports", exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.components = build_components(settings)
    logging.getLogger("agentos").info(
        "agentos-core ready — profile=%s backend=%s",
        settings.profile, settings.llm_backend,
    )
    yield


app = FastAPI(title="agentos-core", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)

app.mount("/static", StaticFiles(directory="data/exports"), name="static")


@app.get("/")
async def root():
    return {"name": "agentos-core", "docs": "/docs", "api": settings.api_prefix}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agentos.main:app", host="0.0.0.0", port=8000, reload=True)
