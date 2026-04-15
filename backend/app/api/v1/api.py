from fastapi import APIRouter
from .chat import router as chat_router
from .runs import router as runs_router
from .memory import router as memory_router
from .tools import router as tools_router

api_router = APIRouter()

@api_router.get("/health")
async def health():
    return {"status": "ok"}

api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(runs_router, prefix="/runs", tags=["runs"])
api_router.include_router(memory_router, prefix="/memory", tags=["memory"])
api_router.include_router(tools_router, prefix="/tools", tags=["tools"])
