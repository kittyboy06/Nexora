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
from backend.app.skills.router import router as skills_router
from backend.app.skills.manager import SkillManager
from backend.app.skills.discovery import GitHubDiscoveryService
from backend.app.skills.composer import SkillPromptComposer
from backend.app.mcp.router import router as mcp_router
from backend.app.mcp.vault import McpVaultService
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.session import McpSessionPool
from backend.app.research.evidence import ResearchEvidenceStore
from backend.app.research.quarantine import QuarantineManager
from backend.app.research.router import router as research_router
from backend.app.research.service import BrowserResearchService
from backend.app.research.tools import register_research_tools
from backend.app.sandbox.bridge import GeneratedToolBridgeManager
from backend.app.sandbox.evidence import SandboxEvidenceStore
from backend.app.sandbox.registry import GeneratedToolRegistry
from backend.app.sandbox.router import router as sandbox_router
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.sandbox.service import SandboxOrchestrationService
from backend.app.sandbox.validator import AstSecurityValidator
from backend.app.memory.backup import MemoryBackupService
from backend.app.memory.database import MemoryDatabase
from backend.app.memory.retrieval import MemoryRetrievalEngine
from backend.app.memory.router import router as memory_router
from backend.app.memory.service import MemoryService
from backend.app.memory.store import DurableMemoryStore
from backend.app.memory.tools import register_memory_tools
from backend.app.desktop.router import router as desktop_router
from backend.app.desktop.service import DesktopService
from backend.app.desktop.tools import register_desktop_tools
from backend.app.scheduler.router import router as scheduler_router
from backend.app.scheduler.service import SchedulerService
from backend.app.agent.executor import Executor
from backend.app.agent.fleet.coordinator import FleetCoordinator
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

    # Initialize Phase 11 Memory and Persistence Platform
    memory_db = MemoryDatabase(db_path=settings.get_memory_data_dir() / "nexora_memory.db")
    memory_store = DurableMemoryStore(database=memory_db)
    memory_retrieval_engine = MemoryRetrievalEngine(store=memory_store, database=memory_db)
    memory_backup_service = MemoryBackupService(database=memory_db, backup_dir=settings.get_memory_data_dir() / "backups")
    memory_service = MemoryService(
        store=memory_store,
        retrieval_engine=memory_retrieval_engine,
        backup_service=memory_backup_service,
        database=memory_db,
    )
    register_memory_tools(tool_registry, memory_retrieval_engine, memory_store)

    app.state.memory_db = memory_db
    app.state.memory_store = memory_store
    app.state.memory_retrieval_engine = memory_retrieval_engine
    app.state.memory_backup_service = memory_backup_service
    app.state.memory_service = memory_service

    # Initialize Phase 12 Desktop Vision and Interaction Platform
    desktop_service = DesktopService(
        quarantine_dir=settings.get_desktop_quarantine_dir(),
    )
    register_desktop_tools(
        tool_registry=tool_registry,
        session_manager=desktop_service.session_manager,
        tree_inspector=desktop_service.tree_inspector,
        capture_broker=desktop_service.capture_broker,
        executor=desktop_service.executor,
        emergency_manager=desktop_service.emergency_manager,
    )
    app.state.desktop_service = desktop_service

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
        memory_service=memory_service,
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

    # Initialize Phase 7 Skills & GitHub Discovery
    skill_manager = SkillManager(settings.get_skills_data_dir())
    github_discovery = GitHubDiscoveryService(token=settings.GITHUB_TOKEN)
    skill_composer = SkillPromptComposer(manager=skill_manager)
    app.state.skill_manager = skill_manager
    app.state.github_discovery = github_discovery
    app.state.skill_composer = skill_composer

    # Initialize Phase 8 Universal MCP Platform
    mcp_vault = McpVaultService(settings.get_mcp_data_dir())
    mcp_registry = McpServerRegistry(settings.get_mcp_data_dir())
    mcp_session_pool = McpSessionPool(
        registry=mcp_registry,
        vault=mcp_vault,
        idle_timeout_seconds=settings.MCP_IDLE_TIMEOUT_SECONDS,
    )
    app.state.mcp_vault = mcp_vault
    app.state.mcp_registry = mcp_registry
    app.state.mcp_session_pool = mcp_session_pool

    # Initialize Phase 9 Browser and Internet Research Service
    research_evidence_store = ResearchEvidenceStore(settings.get_research_data_dir())
    quarantine_manager = QuarantineManager(settings.get_quarantine_data_dir())
    research_service = BrowserResearchService(
        evidence_store=research_evidence_store,
        quarantine_mgr=quarantine_manager,
        vault=mcp_vault,
    )
    register_research_tools(tool_registry, research_service)
    app.state.research_evidence_store = research_evidence_store
    app.state.quarantine_manager = quarantine_manager
    app.state.research_service = research_service

    # Initialize Phase 10 Generated Tools and Sandbox Platform
    sandbox_validator = AstSecurityValidator()
    sandbox_runner = Win32JobObjectRunner(base_sandbox_dir=settings.get_sandbox_data_dir())
    sandbox_evidence_store = SandboxEvidenceStore(runs_dir=settings.get_sandbox_data_dir() / "runs")
    sandbox_service = SandboxOrchestrationService(
        validator=sandbox_validator,
        runner=sandbox_runner,
        evidence_store=sandbox_evidence_store,
    )
    generated_tool_registry = GeneratedToolRegistry(catalog_dir=settings.get_generated_tools_dir())
    generated_tool_bridge = GeneratedToolBridgeManager(
        generated_registry=generated_tool_registry,
        tool_registry=tool_registry,
        runner=sandbox_runner,
    )
    generated_tool_bridge.sync_all()

    app.state.sandbox_validator = sandbox_validator
    app.state.sandbox_runner = sandbox_runner
    app.state.sandbox_evidence_store = sandbox_evidence_store
    app.state.sandbox_service = sandbox_service
    app.state.generated_tool_registry = generated_tool_registry
    app.state.generated_tool_bridge = generated_tool_bridge

    fleet_coordinator = FleetCoordinator(
        tool_registry=tool_registry,
        guard=guard,
        skill_composer=skill_composer,
    )
    app.state.fleet_coordinator = fleet_coordinator
    orchestrator = AgentOrchestrator(
        state_manager=state_manager,
        planner=planner,
        executor=executor,
        evaluator=evaluator,
        settings=settings,
        fleet_coordinator=fleet_coordinator,
    )
    task_manager = TaskManager(
        state_manager=state_manager,
        orchestrator=orchestrator,
        permissions=permission_manager,
    )
    app.state.task_manager = task_manager
    scheduler_service = SchedulerService.create_default(task_manager=task_manager)
    await scheduler_service.start()
    app.state.scheduler_service = scheduler_service
    logger.info("Phase 2, 3, 6, 7, and 8 Agent Engine components initialized.")

    yield

    # Clean shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    await mcp_session_pool.disconnect_all()
    await scheduler_service.stop()
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
    app.include_router(skills_router, prefix="/api")
    app.include_router(mcp_router, prefix="/api")
    app.include_router(research_router)
    app.include_router(sandbox_router)
    app.include_router(memory_router)
    app.include_router(desktop_router)
    app.include_router(scheduler_router)

    return app


app = create_app()
