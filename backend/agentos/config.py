"""Configuration loaded from environment variables with profile support.

Two profiles:
  - minimal: offline demo. Mock LLM, SQLite, one builtin tool. No network.
  - full:    enables an Ollama backend (local or cloud) and optional tools.

The profile actually rewrites behavior (see `apply_profile`): it flips the
relevant feature flags rather than being a documentation-only label.

All feature toggles are explicit fields so ablations are just env overrides.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTOS_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # Profile selection
    profile: str = Field(default="minimal", description="minimal | full")

    # LLM
    llm_backend: str = Field(default="mock", description="mock | ollama")
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:31b-cloud"
    # Optional API key header, for cases where the Ollama endpoint is
    # behind an auth-proxy. For cloud models via the local daemon the
    # user runs `ollama signin` instead and leaves this empty.
    ollama_api_key: str = ""

    # Storage
    db_path: str = "./data/agentos.db"
    prompt_version: str = "react-context-v1"

    # Feature flags (ablations)
    enable_memory: bool = True
    enable_planner: bool = True
    enable_tools: bool = True
    enable_reflection: bool = True
    enable_llm_judge: bool = False  # use LLM-as-judge for live verification
    enable_otel: bool = False
    force_local_only: bool = False  # Air-Gap Mode: block external tools
    debug_verbose: bool = True     # Controls the backend trace stream

    # Optional integrations
    enable_http_fetch: bool = True
    enable_tavily: bool = False
    enable_mcp_plugins: bool = True
    tavily_api_key: str = ""
    otel_service_name: str = "agentos-core"
    otel_exporter_otlp_endpoint: str = ""
    vram_profile: str = "low"  # low | high
    refusal_patterns: list[str] = [
        "i don't know", "i cannot", "i'm unable", "i was unable", "unable to",
        "i do not have", "i encountered an error", "i don't have enough information",
        "cannot provide accurate", "please retry"
    ]
    
    # Semantic Retrieval & Reranking
    enable_embeddings: bool = True
    enable_reranker: bool = True
    embedding_cache_enabled: bool = True
    retrieval_cache_enabled: bool = True
    embedding_model: str = "nomic-embed-text-v2-moe"
    retrieval_mode: str = "hybrid"  # fts, semantic, hybrid
    semantic_top_k: int = 10
    rerank_top_n: int = 3
    semantic_min_score: float = 0.50

    # Agent loop
    max_steps: int = 4
    eval_pass_threshold: float = 0.6
    context_char_budget: int = 32000  # Default safe floor (32k chars / ~8k tokens)
    memory_search_k: int = 8
    memory_min_salience: float = 0.15
    working_memory_ttl_seconds: int = 3600
    episodic_memory_ttl_seconds: int = 1209600

    # Context packer budget ratios (fraction of context_char_budget spent on
    # each section). Remainder goes to retrieved memory. Tuned for the
    # default 8k budget; expose so ablations / different model sizes can
    # shift the balance without editing source.
    context_developer_ratio: float = 0.15
    context_scratchpad_ratio: float = 0.15
    context_tool_ratio: float = 0.40

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    def apply_profile(self) -> None:
        """Apply profile-derived defaults.

        This is the behavioral difference between `minimal` and `full`:

        - minimal: zero-network demo. Force mock LLM, disable HTTP fetch,
          disable Tavily, disable LLM-as-judge. Tests run here.
        - full: enable the LLM judge (for live verification), keep HTTP
          fetch available, auto-switch to ollama when the backend has
          been left at its mock default.
        """
        ratio_sum = self.context_developer_ratio + self.context_scratchpad_ratio + self.context_tool_ratio
        if ratio_sum >= 1.0:
            raise ValueError(
                f"Context budget ratios sum to {ratio_sum:.2f} "
                f"(developer={self.context_developer_ratio}, "
                f"scratchpad={self.context_scratchpad_ratio}, "
                f"tool={self.context_tool_ratio}). "
                f"They must sum to less than 1.0 to leave room for retrieved memory."
            )

        if self.profile == "beta":
            self.force_local_only = False
            self.llm_backend = "ollama"
            self.debug_verbose = True
            self.enable_llm_judge = True
            self.force_local_only = False
        elif self.profile == "minimal":
            self.llm_backend = "mock"
            self.enable_http_fetch = False
            self.enable_tavily = False
            self.enable_llm_judge = False
            self.force_local_only = True
        elif self.profile == "full":
            if self.llm_backend == "mock":
                self.llm_backend = "ollama"
            self.enable_llm_judge = True

        # VRAM-Profile Dynamic Scaling
        if self.vram_profile == "low":
            self.context_char_budget = 32000
        elif self.vram_profile == "high":
            self.context_char_budget = 128000

    def describe(self) -> dict:
        return {
            "profile": self.profile,
            "llm_backend": self.llm_backend,
            "prompt_version": self.prompt_version,
            "force_local_only": self.force_local_only,
            "debug_verbose": self.debug_verbose,
            "context_char_budget": self.context_char_budget,
            "max_steps": self.max_steps,
            "eval_pass_threshold": self.eval_pass_threshold,
            "vram_profile": self.vram_profile,
            "refusal_patterns": self.refusal_patterns,
            "flags": {
                "memory": self.enable_memory,
                "planner": self.enable_planner,
                "tools": self.enable_tools,
                "reflection": self.enable_reflection,
                "llm_judge": self.enable_llm_judge,
                "http_fetch": self.enable_http_fetch,
                "tavily": self.enable_tavily,
                "mcp_plugins": self.enable_mcp_plugins,
                "otel": self.enable_otel,
                "embeddings": self.enable_embeddings,
                "reranker": self.enable_reranker,
                "embedding_cache": self.embedding_cache_enabled,
                "retrieval_cache": self.retrieval_cache_enabled,
            },
        }


settings = Settings()
settings.apply_profile()
