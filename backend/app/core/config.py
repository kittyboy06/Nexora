from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = "NEXORA"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Ollama LLM Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = 3.0
    OLLAMA_INFERENCE_TIMEOUT_SECONDS: float = 120.0

    # GPU & Concurrency Protection
    INFERENCE_CONCURRENCY_LIMIT: int = 1
    INFERENCE_SEMAPHORE_TIMEOUT_SECONDS: float = 5.0

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "data/logs/nexora_backend.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_log_file_path(self) -> Path:
        """Resolve log file path relative to workspace or as absolute."""
        p = Path(self.LOG_FILE_PATH)
        if p.is_absolute():
            return p
        # Check if running inside backend/ or from workspace root
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
