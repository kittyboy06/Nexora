import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.routes.agent import router as agent_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.ollama import router as ollama_router
from backend.app.agent.executor import Executor
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.plan_validator import PlanValidator
from backend.app.agent.planner import Planner
from backend.app.agent.result_evaluator import ResultEvaluator
from backend.app.agent.state_manager import StateManager
from backend.app.agent.task_manager import TaskManager
from backend.app.core.config import get_settings
from backend.app.core.exceptions import NexoraException
from backend.app.core.guard import InferenceGuard
from backend.app.core.logging import setup_logging
from backend.app.models.common import ErrorDetail, ErrorResponse
from backend.app.permissions.manager import PermissionManager
from backend.app.services.app_service import AppService
from backend.app.services.filesystem_service import FilesystemService
from backend.app.services.model_registry import ModelProfileRegistry
from backend.app.services.ollama_service import OllamaService
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.filesystem import register_filesystem_tools
from backend.app.tools.mock_tools import register_mock_tools
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.terminal import register_terminal_tools
from backend.app.tools.windows import register_windows_tools

logger = logging.getLogger("nexora.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing logger, HTTP client, and concurrency guard."""
    settings = get_settings()
    setup_logging(settings)
    logger.info("Starting %s v%s in %s mode", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)

    # Initialize shared AsyncClient
    client = httpx.AsyncClient(
        base_url=settings.OLLAMA_BASE_URL,
        timeout=httpx.Timeout(
            timeout=settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS,
            connect=settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
        ),
    )
    app.state.http_client = client

    # Initialize GPU inference concurrency guard
    guard = InferenceGuard(
        limit=settings.INFERENCE_CONCURRENCY_LIMIT,
        timeout=settings.INFERENCE_SEMAPHORE_TIMEOUT_SECONDS,
    )
    app.state.inference_guard = guard
    logger.info("Inference guard initialized with concurrency limit: %d", guard.limit)

    # Initialize StateManager & Run Startup Recovery Sweep
    state_manager = StateManager(settings=settings)
    recovered_count = await state_manager.recover_on_startup()
    app.state.state_manager = state_manager
    if recovered_count > 0:
        logger.warning("Startup recovery: %d unfinalized tasks marked INTERRUPTED.", recovered_count)

    # Initialize Phase 2 & 3 Agent Engine Components
    tool_registry = ToolRegistry()
    register_mock_tools(tool_registry)

    fs_service = FilesystemService(
        workspace_root=settings.get_workspace_dir(),
        max_file_size_bytes=settings.MAX_FILE_SIZE_BYTES,
    )
    register_filesystem_tools(tool_registry, fs_service)
    app_service = AppService(settings=settings)
    register_windows_tools(tool_registry, app_service)
    terminal_service = TerminalService(
        settings=settings,
        workspace_root=settings.get_workspace_dir(),
    )
    register_terminal_tools(tool_registry, terminal_service)
    app.state.filesystem_service = fs_service
    app.state.app_service = app_service
    app.state.terminal_service = terminal_service
    app.state.tool_registry = tool_registry

    ollama_service = OllamaService(client=client, settings=settings)
    plan_validator = PlanValidator(registry=tool_registry, settings=settings)
    model_profile_registry = ModelProfileRegistry(settings)
    app.state.model_profile_registry = model_profile_registry
    planner = Planner(
        ollama_service=ollama_service,
        validator=plan_validator,
        registry=tool_registry,
        settings=settings,
        guard=guard,
        model_profiles=model_profile_registry,
    )
    permission_manager = PermissionManager(settings=settings)
    executor = Executor(
        registry=tool_registry,
        permissions=permission_manager,
        state_manager=state_manager,
        settings=settings,
    )
    evaluator = ResultEvaluator(
        ollama_service=ollama_service,
        registry=tool_registry,
        guard=guard,
    )
    orchestrator = AgentOrchestrator(
        state_manager=state_manager,
        planner=planner,
        executor=executor,
        evaluator=evaluator,
        settings=settings,
    )
    task_manager = TaskManager(
        state_manager=state_manager,
        orchestrator=orchestrator,
        permissions=permission_manager,
    )
    app.state.task_manager = task_manager
    logger.info("Phase 2 Agent Engine components initialized.")

    yield

    # Clean shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    await client.aclose()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Factory function creating and configuring the FastAPI instance."""
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Local Autonomous Intelligence - Core Backend API",
        lifespan=lifespan,
    )

    # Local CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(NexoraException)
    async def nexora_exception_handler(_: Request, exc: NexoraException):
        error_resp = ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details)
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_resp.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                details=exc.errors(),
            )
        )
        return JSONResponse(status_code=422, content=error_resp.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            )
        )
        return JSONResponse(status_code=exc.status_code, content=error_resp.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("Unhandled server exception: %s", exc)
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred.",
            )
        )
        return JSONResponse(status_code=500, content=error_resp.model_dump(mode="json"))

    # Register API Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(ollama_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(agent_router, prefix="/api")

    return app


app = create_app()
