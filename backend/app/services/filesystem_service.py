import datetime
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from backend.app.core.exceptions import (
    FileAlreadyExistsException,
    FileTooLargeException,
    PathTraversalException,
)

logger = logging.getLogger("nexora.filesystem")


class FilesystemService:
    """Service providing secure, sandboxed filesystem access strictly confined to workspace."""

    def __init__(self, workspace_root: Path, max_file_size_bytes: int = 5_000_000):
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.max_file_size_bytes = max_file_size_bytes

    def resolve_path(self, user_path: str, must_exist: bool = False) -> Path:
        """
        Resolve and canonicalize a path against the workspace jail.
        Raises PathTraversalException if the path resolves outside the workspace.
        """
        # Strip Windows drive letters or leading slashes to prevent root-relative jumping
        clean_path = user_path.lstrip("\\/ ")
        if ":" in clean_path:
            # Handle drive letter attempts like 'C:\evil'
            clean_path = clean_path.split(":", 1)[1].lstrip("\\/ ")

        target = (self.workspace_root / clean_path).resolve()

        if not target.is_relative_to(self.workspace_root):
            logger.warning("Path traversal attempt blocked: '%s' -> '%s'", user_path, target)
            raise PathTraversalException(
                message=f"Access denied: path '{user_path}' escapes workspace sandbox.",
                details={"requested_path": user_path, "resolved_path": str(target)},
            )

        if must_exist and not target.exists():
            raise FileNotFoundError(f"File or directory '{user_path}' does not exist.")

        return target

    def list_dir(self, path: str = ".") -> dict[str, Any]:
        """List files and directories within a workspace subfolder."""
        target = self.resolve_path(path, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(f"Path '{path}' is not a directory.")

        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            stat = item.stat()
            modified = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat()
            entries.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size_bytes": stat.st_size if not item.is_dir() else None,
                "modified_at": modified,
            })

        rel_display = str(target.relative_to(self.workspace_root)).replace("\\", "/")
        return {"path": rel_display if rel_display != "." else "", "count": len(entries), "entries": entries}

    def search_files(self, pattern: str, path: str = ".") -> dict[str, Any]:
        """Search workspace recursively using glob pattern."""
        target = self.resolve_path(path, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(f"Search path '{path}' must be a directory.")

        matches = []
        for match in target.rglob(pattern):
            if match.is_relative_to(self.workspace_root):
                rel_path = str(match.relative_to(self.workspace_root)).replace("\\", "/")
                matches.append({
                    "path": rel_path,
                    "name": match.name,
                    "is_dir": match.is_dir(),
                    "size_bytes": match.stat().st_size if match.is_file() else None,
                })

        return {"pattern": pattern, "match_count": len(matches), "matches": matches[:100]}

    def read_file(self, path: str, max_bytes: int = 5_000_000) -> dict[str, Any]:
        """Read content of a text file inside workspace with size limits."""
        target = self.resolve_path(path, must_exist=True)
        if not target.is_file():
            raise IsADirectoryError(f"Target '{path}' is a directory, not a file.")

        size = target.stat().st_size
        effective_limit = min(max_bytes, self.max_file_size_bytes)
        if size > effective_limit:
            raise FileTooLargeException(
                message=f"File size ({size} bytes) exceeds maximum limit ({effective_limit} bytes).",
                details={"file_size": size, "limit": effective_limit},
            )

        content = target.read_text(encoding="utf-8", errors="replace")
        rel_display = str(target.relative_to(self.workspace_root)).replace("\\", "/")
        return {"path": rel_display, "size_bytes": size, "content": content}

    def create_file(self, path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        """Create a new file within workspace."""
        target = self.resolve_path(path)
        if target.exists() and not overwrite:
            raise FileAlreadyExistsException(
                message=f"File '{path}' already exists. Pass overwrite=True to replace.",
                details={"path": path},
            )

        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self.max_file_size_bytes:
            raise FileTooLargeException(
                message=f"Content size ({len(content_bytes)} bytes) exceeds limit ({self.max_file_size_bytes} bytes)."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("Created file: %s (size=%d bytes, overwrite=%s)", target, len(content_bytes), overwrite)

        rel_display = str(target.relative_to(self.workspace_root)).replace("\\", "/")
        return {"path": rel_display, "size_bytes": len(content_bytes), "overwritten": overwrite}

    def edit_file(self, path: str, target_text: str, replacement_text: str) -> dict[str, Any]:
        """Replace target substring in existing file."""
        target_path = self.resolve_path(path, must_exist=True)
        if not target_path.is_file():
            raise IsADirectoryError(f"Target '{path}' is not a file.")

        original = target_path.read_text(encoding="utf-8")
        if target_text not in original:
            raise ValueError(f"Target text not found in '{path}'.")

        occurrences = original.count(target_text)
        updated = original.replace(target_text, replacement_text)
        target_path.write_text(updated, encoding="utf-8")
        logger.info("Edited file: %s (%d occurrences replaced)", target_path, occurrences)

        rel_display = str(target_path.relative_to(self.workspace_root)).replace("\\", "/")
        return {"path": rel_display, "replacements_count": occurrences, "new_size_bytes": len(updated.encode('utf-8'))}

    def rename_file(self, source: str, target_name: str) -> dict[str, Any]:
        """Rename a file or folder in place."""
        src_path = self.resolve_path(source, must_exist=True)
        # Target name must be a single filename or relative path in workspace
        dst_path = self.resolve_path(target_name)
        if dst_path.exists():
            raise FileAlreadyExistsException(f"Destination '{target_name}' already exists.")

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)
        logger.info("Renamed '%s' to '%s'", src_path, dst_path)

        return {
            "source": str(src_path.relative_to(self.workspace_root)).replace("\\", "/"),
            "destination": str(dst_path.relative_to(self.workspace_root)).replace("\\", "/"),
        }

    def copy_file(self, source: str, destination: str, overwrite: bool = False) -> dict[str, Any]:
        """Copy a file within the workspace."""
        src_path = self.resolve_path(source, must_exist=True)
        dst_path = self.resolve_path(destination)
        if dst_path.exists() and not overwrite:
            raise FileAlreadyExistsException(f"Destination '{destination}' already exists.")

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, dirs_exist_ok=overwrite)
        else:
            shutil.copy2(src_path, dst_path)

        logger.info("Copied '%s' to '%s'", src_path, dst_path)
        return {
            "source": str(src_path.relative_to(self.workspace_root)).replace("\\", "/"),
            "destination": str(dst_path.relative_to(self.workspace_root)).replace("\\", "/"),
            "overwritten": overwrite,
        }

    def move_file(self, source: str, destination: str, overwrite: bool = False) -> dict[str, Any]:
        """Move a file within the workspace."""
        src_path = self.resolve_path(source, must_exist=True)
        dst_path = self.resolve_path(destination)
        if dst_path.exists() and not overwrite:
            raise FileAlreadyExistsException(f"Destination '{destination}' already exists.")

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_path, dst_path)
        logger.info("Moved '%s' to '%s'", src_path, dst_path)

        return {
            "source": str(src_path.relative_to(self.workspace_root)).replace("\\", "/"),
            "destination": str(dst_path.relative_to(self.workspace_root)).replace("\\", "/"),
        }

    def delete_file(self, path: str, recursive: bool = False) -> dict[str, Any]:
        """Delete a file or directory within workspace."""
        target = self.resolve_path(path, must_exist=True)
        if target == self.workspace_root:
            raise PermissionError("Cannot delete workspace root directory.")

        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
        else:
            target.unlink()

        logger.info("Deleted '%s' (recursive=%s)", target, recursive)
        return {"path": path, "deleted": True, "recursive": recursive}
