from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "AgentOS"
    API_V1_STR: str = "/api/v1"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4:31b-cloud"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text-v2-moe"

    # Tavily
    TAVILY_API_KEY: str = ""

    # MCP Server Credentials
    GITHUB_TOKEN: str = ""
    HF_TOKEN: str = ""

    # Databases
    CHROMA_DB_PATH: str = "./data/chroma"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Observability
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # --- Agent loop ---
    MAX_ITERATIONS: int = 3
    EVAL_PASS_THRESHOLD: float = 0.7
    CONTEXT_BUDGET_CHARS: int = 12000        # max chars of tool+memory context fed to planner
    TOOL_OUTPUT_MAX_CHARS: int = 5000        # max chars per individual tool output
    MCP_RESULT_MAX_CHARS: int = 3000         # max chars per MCP result
    SEARCH_RESULT_PREVIEW: int = 300         # chars per search result snippet
    VECTOR_SEARCH_K: int = 3                 # number of vector memory results
    EPISODIC_SEARCH_K: int = 2               # number of episodic memory results
    GRAPH_SEARCH_K: int = 3                  # number of graph traversal results
    MAX_MESSAGE_LENGTH: int = 10000          # max user message length

    # --- LLM retry ---
    LLM_MAX_RETRIES: int = 2
    LLM_RETRY_DELAY: float = 2.0            # seconds between retries

    # --- Reranking ---
    RERANK_FETCH_MULTIPLIER: int = 3        # fetch k*multiplier candidates, rerank to k
    RERANK_MODEL: str = "ms-marco-MiniLM-L-12-v2"  # FlashRank model (~33MB)

    # --- Memory consolidation ---
    CONSOLIDATION_PRUNE_THRESHOLD: float = 0.3  # tasks below this score get pruned
    CONSOLIDATION_COMPRESS_MIN_CHARS: int = 500  # only compress episodes longer than this


settings = Settings()
