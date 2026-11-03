"""Tool to install a package dependency."""

from typing import Any
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.services.terminal_service import TerminalService
from backend.app.tools.base import BaseTool


class TerminalInstallPackageArgs(BaseModel):
    package_name: str = Field(..., description="Name of the package or library to install.")
    manager: str = Field(default="pip", description="Package manager to use: 'pip' or 'npm'.")
    upgrade: bool = Field(default=False, description="Whether to upgrade package to the latest version.")


class TerminalInstallPackageTool(BaseTool):
    """Install or upgrade a package dependency. Sensitive operation requiring approval."""

    name = "terminal_install_package"
    description = "Install or upgrade a package dependency using pip or npm. Requires human approval."
    risk_level = RiskLevel.SENSITIVE
    args_schema = TerminalInstallPackageArgs

    def __init__(self, service: TerminalService):
        self._service = service

    async def execute(self, package_name: str, manager: str = "pip", upgrade: bool = False, **kwargs: Any) -> dict[str, Any]:
        return await self._service.install_package(package_name=package_name, manager=manager, upgrade=upgrade)
