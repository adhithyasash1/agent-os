from __future__ import annotations

from .mock import MockLLM
from .ollama import OllamaLLM
from .protocol import LLM


VRAM_LIMITS = {
    "low": 32768,      # 32k tokens (~130k chars)
    "high": 131072,    # 131k tokens (~520k chars)
}

def build_llm(settings) -> LLM:
    if settings.llm_backend == "ollama":
        # Rule of thumb: 1 token approx 4 chars. Add 2k tokens overhead for prompt.
        # Note: This is a heuristic. For JSON or code-heavy research, local density
        # can drop to ~3 chars/token. We over-provision by 2k tokens to compensate.
        budget_tokens = (settings.context_char_budget // 4) + 2048
        limit = VRAM_LIMITS.get(settings.vram_profile, 32768)
        num_ctx = min(budget_tokens, limit)
        
        return OllamaLLM(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            api_key=settings.ollama_api_key or None,
            num_ctx=num_ctx,
        )
    return MockLLM()
