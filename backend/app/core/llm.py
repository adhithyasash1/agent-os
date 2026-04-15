from langchain_ollama import ChatOllama
from app.core.config import settings

def get_llm():
    is_cloud = settings.OLLAMA_MODEL.endswith(":cloud") or "-cloud" in settings.OLLAMA_MODEL
    kwargs = {
        "model": settings.OLLAMA_MODEL,
        "base_url": settings.OLLAMA_BASE_URL,
        "temperature": 0,
        "timeout": 300,
    }
    # Only set num_predict for local models; cloud models manage their own limits
    if not is_cloud:
        kwargs["num_predict"] = 4096
    return ChatOllama(**kwargs)

def get_embeddings():
    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBED_MODEL,
        base_url=settings.OLLAMA_BASE_URL
    )
