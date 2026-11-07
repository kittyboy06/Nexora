from functools import lru_cache
import httpx
from fastapi import Depends, Request

from backend.app.agent.executor import Executor
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.plan_validator import PlanValidator
from backend.app.agent.planner import Planner
from backend.app.agent.result_evaluator import ResultEvaluator
from backend.app.agent.state_manager import StateManager
from backend.app.agent.task_manager import TaskManager
from backend.app.core.config import Settings, get_settings
from backend.app.core.guard import InferenceGuard
from backend.app.permissions.manager import PermissionManager
from backend.app.services.app_service import AppService
from backend.app.services.filesystem_service import FilesystemService
from backend.app.services.model_registry import ModelProfileRegistry
from backend.app.services.ollama_service import OllamaService
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.filesystem import register_filesystem_tools
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.terminal import register_terminal_tools
from backend.app.tools.windows import register_windows_tools


def get_app_settings() -> Settings:
    """Dependency provider for cached application settings."""
    return get_settings()


def get_filesystem_service(
    settings: Settings = Depends(get_app_settings),
) -> FilesystemService:
    """Dependency provider for FilesystemService."""
    return FilesystemService(
        workspace_root=settings.get_workspace_dir(),
        max_file_size_bytes=settings.MAX_FILE_SIZE_BYTES,
    )


def get_app_service(
    settings: Settings = Depends(get_app_settings),
) -> AppService:
    """Dependency provider for AppService."""
    return AppService(settings=settings)


def get_terminal_service(
    settings: Settings = Depends(get_app_settings),
) -> TerminalService:
    """Dependency provider for TerminalService."""
    return TerminalService(
        settings=settings,
        workspace_root=settings.get_workspace_dir(),
    )


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency provider for the shared application httpx client."""
    client: httpx.AsyncClient = getattr(request.app.state, "http_client", None)
    if client is None:
        raise RuntimeError("Application HTTP client has not been initialized in lifespan.")
    return client


def get_inference_guard(request: Request) -> InferenceGuard:
    """Dependency provider for the GPU concurrency guard."""
    guard: InferenceGuard = getattr(request.app.state, "inference_guard", None)
    if guard is None:
        raise RuntimeError("InferenceGuard has not been initialized in lifespan.")
    return guard


def get_ollama_service(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_app_settings),
) -> OllamaService:
    """Dependency provider for OllamaService instance."""
    service: OllamaService = getattr(request.app.state, "ollama_service", None)
    if service is None or getattr(service, "client", None) != client:
        service = OllamaService(client=client, settings=settings)
        request.app.state.ollama_service = service
    return service


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Singleton ToolRegistry populated with Phase 2 mock tools and Phase 3 real tools."""
    settings = get_settings()
    registry = ToolRegistry()
    fs_service = FilesystemService(
        workspace_root=settings.get_workspace_dir(),
        max_file_size_bytes=settings.MAX_FILE_SIZE_BYTES,
    )
    register_filesystem_tools(registry, fs_service)
    app_service = AppService(settings=settings)
    register_windows_tools(registry, app_service)
    terminal_service = TerminalService(
        settings=settings,
        workspace_root=settings.get_workspace_dir(),
    )
    register_terminal_tools(registry, terminal_service)
    return registry


def get_state_manager(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> StateManager:
    """Dependency provider for application StateManager."""
    sm: StateManager = getattr(request.app.state, "state_manager", None)
    if sm is None:
        sm = StateManager(settings=settings)
        request.app.state.state_manager = sm
    return sm


def get_permission_manager(
    settings: Settings = Depends(get_app_settings),
) -> PermissionManager:
    """Dependency provider for PermissionManager."""
    return PermissionManager(settings=settings)


def get_plan_validator(
    registry: ToolRegistry = Depends(get_tool_registry),
    settings: Settings = Depends(get_app_settings),
) -> PlanValidator:
    """Dependency provider for PlanValidator."""
    return PlanValidator(registry=registry, settings=settings)


_model_profile_registry: ModelProfileRegistry | None = None


def get_model_profile_registry(
    settings: Settings = Depends(get_app_settings),
) -> ModelProfileRegistry:
    """Dependency provider for ModelProfileRegistry."""
    global _model_profile_registry
    if _model_profile_registry is None or _model_profile_registry.settings.MODEL_PROFILES_FILE != settings.MODEL_PROFILES_FILE:
        _model_profile_registry = ModelProfileRegistry(settings)
    return _model_profile_registry


def get_planner(
    ollama: OllamaService = Depends(get_ollama_service),
    validator: PlanValidator = Depends(get_plan_validator),
    registry: ToolRegistry = Depends(get_tool_registry),
    settings: Settings = Depends(get_app_settings),
    guard: InferenceGuard = Depends(get_inference_guard),
    model_profiles: ModelProfileRegistry = Depends(get_model_profile_registry),
) -> Planner:
    """Dependency provider for Planner."""
    return Planner(
        ollama_service=ollama,
        validator=validator,
        registry=registry,
        settings=settings,
        guard=guard,
        model_profiles=model_profiles,
    )


def get_executor(
    registry: ToolRegistry = Depends(get_tool_registry),
    permissions: PermissionManager = Depends(get_permission_manager),
    state_manager: StateManager = Depends(get_state_manager),
    settings: Settings = Depends(get_app_settings),
) -> Executor:
    """Dependency provider for Executor."""
    return Executor(
        registry=registry,
        permissions=permissions,
        state_manager=state_manager,
        settings=settings,
    )


def get_result_evaluator(
    ollama: OllamaService = Depends(get_ollama_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    guard: InferenceGuard = Depends(get_inference_guard),
) -> ResultEvaluator:
    """Dependency provider for ResultEvaluator."""
    return ResultEvaluator(
        ollama_service=ollama,
        registry=registry,
        guard=guard,
    )


def get_orchestrator(
    state_manager: StateManager = Depends(get_state_manager),
    planner: Planner = Depends(get_planner),
    executor: Executor = Depends(get_executor),
    evaluator: ResultEvaluator = Depends(get_result_evaluator),
    settings: Settings = Depends(get_app_settings),
) -> AgentOrchestrator:
    """Dependency provider for AgentOrchestrator."""
    return AgentOrchestrator(
        state_manager=state_manager,
        planner=planner,
        executor=executor,
        evaluator=evaluator,
        settings=settings,
    )


def get_task_manager(
    request: Request,
    state_manager: StateManager = Depends(get_state_manager),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    permissions: PermissionManager = Depends(get_permission_manager),
) -> TaskManager:
    """Dependency provider for application TaskManager."""
    tm: TaskManager = getattr(request.app.state, "task_manager", None)
    if tm is None:
        tm = TaskManager(
            state_manager=state_manager,
            orchestrator=orchestrator,
            permissions=permissions,
        )
        request.app.state.task_manager = tm
    return tm
