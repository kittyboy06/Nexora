import pytest
from backend.app.core.exceptions import (
    FileAlreadyExistsException,
    FileTooLargeException,
    PathTraversalException,
)
from backend.app.models.agent import RiskLevel
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


@pytest.fixture
def fs(tmp_path):
    workspace = tmp_path / "sandbox_workspace"
    workspace.mkdir()
    return FilesystemService(workspace_root=workspace, max_file_size_bytes=100_000)


def test_path_traversal_detection(fs: FilesystemService):
    with pytest.raises(PathTraversalException):
        fs.resolve_path("../outside.txt")

    with pytest.raises(PathTraversalException):
        fs.resolve_path("../../Windows/System32/calc.exe")

    with pytest.raises(PathTraversalException):
        fs.resolve_path("sub/../../escaped.txt")


@pytest.mark.asyncio
async def test_file_create_and_read(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    read_tool = FileReadTool(fs)

    create_res = await create_tool.execute(path="docs/hello.txt", content="Hello, NEXORA!")
    assert create_res["path"] == "docs/hello.txt"
    assert create_res["size_bytes"] == len("Hello, NEXORA!")

    read_res = await read_tool.execute(path="docs/hello.txt")
    assert read_res["content"] == "Hello, NEXORA!"


@pytest.mark.asyncio
async def test_file_create_overwrite_protection(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    await create_tool.execute(path="data.txt", content="Initial")

    # Overwrite = False should fail
    with pytest.raises(FileAlreadyExistsException):
        await create_tool.execute(path="data.txt", content="New data", overwrite=False)

    # Overwrite = True should succeed
    res = await create_tool.execute(path="data.txt", content="New data", overwrite=True)
    assert res["overwritten"] is True


@pytest.mark.asyncio
async def test_file_edit(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    edit_tool = FileEditTool(fs)
    read_tool = FileReadTool(fs)

    await create_tool.execute(path="config.py", content="DEBUG = True\nPORT = 8000")
    edit_res = await edit_tool.execute(path="config.py", target="PORT = 8000", replacement="PORT = 9000")
    assert edit_res["replacements_count"] == 1

    read_res = await read_tool.execute(path="config.py")
    assert "PORT = 9000" in read_res["content"]

    # Target not found raises ValueError
    with pytest.raises(ValueError):
        await edit_tool.execute(path="config.py", target="NONEXISTENT", replacement="X")


@pytest.mark.asyncio
async def test_file_list_and_search(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    list_tool = FileListTool(fs)
    search_tool = FileSearchTool(fs)

    await create_tool.execute(path="src/main.py", content="print('hello')")
    await create_tool.execute(path="src/util.py", content="# util")
    await create_tool.execute(path="src/readme.md", content="# doc")

    list_res = await list_tool.execute(path="src")
    assert list_res["count"] == 3

    search_res = await search_tool.execute(pattern="*.py", path="src")
    assert search_res["match_count"] == 2
    names = [m["name"] for m in search_res["matches"]]
    assert "main.py" in names
    assert "util.py" in names


@pytest.mark.asyncio
async def test_file_rename_copy_move(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    rename_tool = FileRenameTool(fs)
    copy_tool = FileCopyTool(fs)
    move_tool = FileMoveTool(fs)
    read_tool = FileReadTool(fs)

    await create_tool.execute(path="original.txt", content="Original content")

    # Rename
    await rename_tool.execute(source="original.txt", target_name="renamed.txt")
    read_res = await read_tool.execute(path="renamed.txt")
    assert read_res["content"] == "Original content"

    # Copy
    await copy_tool.execute(source="renamed.txt", destination="backup.txt")
    assert (await read_tool.execute(path="backup.txt"))["content"] == "Original content"

    # Move
    await move_tool.execute(source="backup.txt", destination="archive/backup.txt")
    assert (await read_tool.execute(path="archive/backup.txt"))["content"] == "Original content"


@pytest.mark.asyncio
async def test_file_delete(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    delete_tool = FileDeleteTool(fs)

    await create_tool.execute(path="to_delete.txt", content="Goodbye")
    del_res = await delete_tool.execute(path="to_delete.txt")
    assert del_res["deleted"] is True

    # Root directory cannot be deleted
    with pytest.raises(PermissionError):
        await delete_tool.execute(path=".")


@pytest.mark.asyncio
async def test_file_too_large(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    large_content = "X" * 150_000  # Exceeds max 100_000
    with pytest.raises(FileTooLargeException):
        await create_tool.execute(path="huge.txt", content=large_content)


def test_dynamic_risk_level(fs: FilesystemService):
    create_tool = FileCreateTool(fs)
    assert create_tool.get_risk_level({"overwrite": False}) == RiskLevel.CONTROLLED
    assert create_tool.get_risk_level({"overwrite": True}) == RiskLevel.SENSITIVE

    delete_tool = FileDeleteTool(fs)
    assert delete_tool.get_risk_level({}) == RiskLevel.SENSITIVE

    read_tool = FileReadTool(fs)
    assert read_tool.get_risk_level({}) == RiskLevel.SAFE
