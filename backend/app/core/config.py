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
    OLLAMA_MODEL: str = ""
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = 3.0
    OLLAMA_INFERENCE_TIMEOUT_SECONDS: float = 120.0
    MODEL_ROUTER_MODEL: str = ""
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

    # Phase 8 Universal MCP Platform
    MCP_DATA_DIR: str = "data/mcp"
    MCP_IDLE_TIMEOUT_SECONDS: float = 600.0
    MCP_TOOL_TIMEOUT_SECONDS: float = 30.0

    # Phase 9 Browser and Internet Research
    RESEARCH_DATA_DIR: str = "data/research"
    QUARANTINE_DATA_DIR: str = "data/quarantine"

    # Phase 10 Generated Tools & Sandbox
    SANDBOX_DATA_DIR: str = "data/sandbox"
    GENERATED_TOOLS_DIR: str = "data/tools/generated"

    # Phase 11 Memory and Persistence
    MEMORY_DATA_DIR: str = "data/memory"

    # Phase 12 Desktop Vision and Interaction
    DESKTOP_QUARANTINE_DIR: str = "data/quarantine/desktop"

    # Phase 13 Scheduler and Background Work
    SCHEDULER_DATA_DIR: str = "data/scheduler"

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

    def get_mcp_data_dir(self) -> Path:
        """Resolve data/mcp directory relative to workspace or absolute."""
        p = Path(self.MCP_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_research_data_dir(self) -> Path:
        """Resolve data/research directory relative to workspace or absolute."""
        p = Path(self.RESEARCH_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_quarantine_data_dir(self) -> Path:
        """Resolve data/quarantine directory relative to workspace or absolute."""
        p = Path(self.QUARANTINE_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_sandbox_data_dir(self) -> Path:
        """Resolve data/sandbox directory relative to workspace or absolute."""
        p = Path(self.SANDBOX_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_generated_tools_dir(self) -> Path:
        """Resolve data/tools/generated directory relative to workspace or absolute."""
        p = Path(self.GENERATED_TOOLS_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_memory_data_dir(self) -> Path:
        """Resolve data/memory directory relative to workspace or absolute."""
        p = Path(self.MEMORY_DATA_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_desktop_quarantine_dir(self) -> Path:
        """Resolve desktop screenshot quarantine directory path."""
        p = Path(self.DESKTOP_QUARANTINE_DIR)
        if p.is_absolute():
            return p
        if Path.cwd().name == "backend":
            candidate = Path.cwd().parent / p
        else:
            candidate = Path.cwd() / p
        return candidate.resolve()

    def get_scheduler_data_dir(self) -> Path:
        """Resolve data/scheduler directory relative to workspace or absolute."""
        p = Path(self.SCHEDULER_DATA_DIR)
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
