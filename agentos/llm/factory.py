from __future__ import annotations

from .mock import MockLLM
from .ollama import OllamaLLM
from .protocol import LLM


def build_llm(settings) -> LLM:
    if settings.llm_backend == "ollama":
        return OllamaLLM(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            api_key=settings.ollama_api_key or None,
        )
    return MockLLM()
