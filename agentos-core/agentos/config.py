"""Configuration loaded from environment variables with profile support.

Two profiles:
  - minimal: runs with zero external services. Mock LLM, SQLite, one builtin tool.
  - full:    enables Ollama LLM + optional feature flags.

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
    ollama_model: str = "qwen3.5:397b-cloud"

    # Storage
    db_path: str = "./data/agentos.db"
    prompt_version: str = "react-context-v1"

    # Feature flags (ablations)
    enable_memory: bool = True
    enable_planner: bool = True
    enable_tools: bool = True
    enable_reflection: bool = True
    enable_otel: bool = False

    # Optional integrations
    enable_http_fetch: bool = True
    enable_tavily: bool = False
    tavily_api_key: str = ""
    otel_service_name: str = "agentos-core"
    otel_exporter_otlp_endpoint: str = ""

    # Agent loop
    max_steps: int = 4
    eval_pass_threshold: float = 0.6
    context_char_budget: int = 8000
    memory_search_k: int = 8
    memory_min_salience: float = 0.15
    working_memory_ttl_seconds: int = 3600
    episodic_memory_ttl_seconds: int = 1209600

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    def apply_profile(self) -> None:
        """Force dependency-heavy features off in minimal profile."""
        if self.profile == "minimal":
            self.enable_tavily = False

    def describe(self) -> dict:
        return {
            "profile": self.profile,
            "llm_backend": self.llm_backend,
            "prompt_version": self.prompt_version,
            "flags": {
                "memory": self.enable_memory,
                "planner": self.enable_planner,
                "tools": self.enable_tools,
                "reflection": self.enable_reflection,
                "http_fetch": self.enable_http_fetch,
                "tavily": self.enable_tavily,
                "otel": self.enable_otel,
            },
        }


settings = Settings()
settings.apply_profile()
