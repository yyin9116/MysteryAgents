"""
Application settings and configuration.

Loads configuration from environment variables using pydantic-settings.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
    )

    HOST: str = '0.0.0.0'
    PORT: int = 8000
    DEBUG: bool = False

    OPENAI_API_KEY: Optional[str] = None
    ALIBABA_API_KEY: Optional[str] = None
    ALIBABA_BASE_URL: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    ZHIPU_API_KEY: Optional[str] = None
    ZHIPU_BASE_URL: str = 'https://open.bigmodel.cn/api/paas/v4'
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = 'http://localhost:11434'

    MODEL_HIGH_IQ: str = 'openai/gpt-5.5'
    MODEL_MID_IQ: str = 'openai/gpt-5.5'
    MODEL_LOW_IQ: str = 'openai/gpt-5.5'

    MEMORY_PROVIDER: str = 'qdrant'
    QDRANT_HOST: str = 'localhost'
    QDRANT_PORT: int = 6333
    CHROMA_PATH: str = './chroma_db'
    EMBEDDING_MODEL: str = 'sentence-transformers/all-MiniLM-L6-v2'

    MEMORY_DECAY_HIGH: float = 0.05
    MEMORY_DECAY_MID: float = 0.15
    MEMORY_DECAY_LOW: float = 0.30
    MEMORY_CASCADE_PROBABILITY: float = 0.5

    CHECKPOINT_INTERVAL: int = 5
    STORAGE_PATH: str = str(PROJECT_ROOT / 'game_states')

    DATABASE_URL: str = 'sqlite:///./undercover_ai.db'
    USAGE_DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    REDIS_URL: Optional[str] = None
    USAGE_CACHE_ENABLED: bool = True
    USAGE_CACHE_TTL_SECONDS: int = 300
    USAGE_CACHE_PREFIX: str = 'usage'

    CORS_ORIGINS: str = (
        'http://localhost:5173,'
        'http://127.0.0.1:5173,'
        'http://localhost:4173,'
        'http://127.0.0.1:4173'
    )

    LOG_LEVEL: str = 'INFO'

    LITELLM_LOG: str = 'INFO'
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 3

    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_SECONDS: float = 0.5

    DEFAULT_AGENT_COUNT: int = 6
    DEFAULT_ROUND_LIMIT: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]

    def get_storage_path(self) -> Path:
        path = Path(self.STORAGE_PATH).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
