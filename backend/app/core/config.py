from functools import lru_cache
from pathlib import Path
from pydantic import Field
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
    MODEL_ROUTER_MODEL: str = "qwen3.5:9b"
    MODEL_ROUTER_CONFIDENCE_THRESHOLD: float = Field(default=0.65, ge=0.0, le=1.0)
    MODEL_PROFILES_FILE: str = "data/model_profiles.json"

    # GPU & Concurrency Protection
    INFERENCE_CONCURRENCY_LIMIT: int = 1
    INFERENCE_SEMAPHORE_TIMEOUT_SECONDS: float = 5.0

    # Phase 2 Agent Execution Limits
    MAX_PLAN_STEPS: int = 10
    MAX_EXECUTION_ITERATIONS: int = 15
    MAX_RETRIES_PER_STEP: int = 2
    MAX_PLANNING_ATTEMPTS: int = 2
    MAX_EXECUTION_DURATION_SECONDS: float = 300.0
    APPROVAL_EXPIRATION_SECONDS: float = 600.0
    AUTO_APPROVE_CONTROLLED: bool = True
    TASK_DATA_DIR: str = "data/tasks"

    # Phase 7 Skills & GitHub Discovery
    SKILLS_DATA_DIR: str = "data/skills"
    GITHUB_TOKEN: str = ""

    # Phase 3 Real-World Tool Limits
    WORKSPACE_DIR: str = "data/workspace"
    MAX_FILE_SIZE_BYTES: int = 5_000_000  # 5 MB
    ALLOWED_TERMINAL_COMMANDS: list[str] = [
        "python", "pip", "git", "node", "npm", "pytest", "systeminfo", "whoami", "ipconfig"
    ]
    TERMINAL_TIMEOUT_SECONDS: float = 30.0
    MAX_TERMINAL_OUTPUT_BYTES: int = 51_200  # 50 KB
    PROTECTED_PROCESS_NAMES: set[str] = {
        "explorer.exe",
        "svchost.exe",
        "csrss.exe",
        "smss.exe",
        "lsass.exe",
        "services.exe",
        "winlogon.exe",
        "system",
        "system idle process",
        "registry",
        "taskmgr.exe",
        "wininit.exe",
        "dwm.exe",
        "conhost.exe",
        "spoolsv.exe",
        "sihost.exe",
        "fontdrvhost.exe",
    }

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "data/logs/nexora_backend.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_workspace_dir(self) -> Path:
        """Resolve workspace directory relative to project root or absolute."""
        p = Path(self.WORKSPACE_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_task_data_dir(self) -> Path:
        """Resolve data/tasks directory relative to workspace or absolute."""
        p = Path(self.TASK_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_skills_data_dir(self) -> Path:
        """Resolve data/skills directory relative to workspace or absolute."""
        p = Path(self.SKILLS_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_model_profiles_file(self) -> Path:
        """Resolve the editable specialist profile catalogue path."""
        p = Path(self.MODEL_PROFILES_FILE)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

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
