"""NEXORA Filesystem Tools (Milestone 3A)."""

from backend.app.services.filesystem_service import FilesystemService
from backend.app.tools.filesystem.file_copy import FileCopyTool
from backend.app.tools.filesystem.file_create import FileCreateTool
from backend.app.tools.filesystem.file_delete import FileDeleteTool
from backend.app.tools.filesystem.file_edit import FileEditTool
from backend.app.tools.filesystem.file_list import FileListTool
from backend.app.tools.filesystem.file_move import FileMoveTool
from backend.app.tools.filesystem.file_read import FileReadTool
from backend.app.tools.filesystem.file_rename import FileRenameTool
from backend.app.tools.filesystem.file_search import FileSearchTool
from backend.app.tools.registry import ToolRegistry


def register_filesystem_tools(registry: ToolRegistry, fs_service: FilesystemService) -> None:
    """Register all 9 real filesystem tools into the ToolRegistry."""
    registry.register(FileListTool(fs_service))
    registry.register(FileSearchTool(fs_service))
    registry.register(FileReadTool(fs_service))
    registry.register(FileCreateTool(fs_service))
    registry.register(FileEditTool(fs_service))
    registry.register(FileRenameTool(fs_service))
    registry.register(FileCopyTool(fs_service))
    registry.register(FileMoveTool(fs_service))
    registry.register(FileDeleteTool(fs_service))


__all__ = [
    "FileListTool",
    "FileSearchTool",
    "FileReadTool",
    "FileCreateTool",
    "FileEditTool",
    "FileRenameTool",
    "FileCopyTool",
    "FileMoveTool",
    "FileDeleteTool",
    "register_filesystem_tools",
]
