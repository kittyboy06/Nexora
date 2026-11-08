"""Unit tests for Phase 15 Skill Import and Sanitization Service."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.skills.discovery import GitHubDiscoveryService
from backend.app.skills.importer import SkillImportError, SkillImporterService
from backend.app.skills.manager import SkillManager
from backend.app.skills.models import SkillManifest


@pytest.fixture
def temp_skills_dir(tmp_path: Path):
    d = tmp_path / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def skill_manager(temp_skills_dir: Path):
    return SkillManager(base_dir=temp_skills_dir)


@pytest.fixture
def skill_importer(skill_manager: SkillManager):
    return SkillImporterService(manager=skill_manager)


def test_validate_safe_path_rejects_empty_or_invalid(skill_importer: SkillImporterService, tmp_path: Path):
    with pytest.raises(SkillImportError, match="cannot be empty"):
        skill_importer.validate_safe_path("")

    with pytest.raises(SkillImportError, match="does not exist"):
        skill_importer.validate_safe_path(str(tmp_path / "nonexistent_dir_12345"))

    dummy_file = tmp_path / "sample.txt"
    dummy_file.write_text("hello", encoding="utf-8")
    with pytest.raises(SkillImportError, match="not a directory"):
        skill_importer.validate_safe_path(str(dummy_file))


def test_import_from_folder_with_frontmatter(skill_importer: SkillImporterService, tmp_path: Path):
    folder = tmp_path / "custom-git-skill"
    folder.mkdir()
    skill_md = folder / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "id: git-wizard\n"
        "name: Git Wizard\n"
        "version: 1.2.0\n"
        "description: Master git operations with ease.\n"
        "tags: [git, vcs]\n"
        "---\n"
        "# Git Wizard Instructions\n"
        "Always check git status before committing.\n",
        encoding="utf-8",
    )

    bundle = skill_importer.import_from_folder(str(folder), enable_immediately=False)

    assert bundle.manifest.id == "git-wizard"
    assert bundle.manifest.version == "1.2.0"
    assert bundle.is_enabled is False  # Fail-closed default
    assert "Always check git status" in bundle.instructions
    assert bundle.provenance.source_url.startswith("local://")


def test_import_from_folder_with_separate_manifest(skill_importer: SkillImporterService, tmp_path: Path):
    folder = tmp_path / "docker-helper"
    folder.mkdir()
    manifest_file = folder / "manifest.json"
    manifest_file.write_text(
        '{\n'
        '  "id": "docker-helper",\n'
        '  "name": "Docker Helper",\n'
        '  "version": "2.0.0",\n'
        '  "description": "Container operations guidance",\n'
        '  "tags": ["docker", "containers"]\n'
        '}\n',
        encoding="utf-8",
    )
    skill_md = folder / "SKILL.md"
    skill_md.write_text("Guidance for Docker compose files.", encoding="utf-8")

    bundle = skill_importer.import_from_folder(str(folder), enable_immediately=True)

    assert bundle.manifest.id == "docker-helper"
    assert bundle.manifest.version == "2.0.0"
    assert bundle.is_enabled is True  # Explicitly enabled


def test_import_from_paste(skill_importer: SkillImporterService):
    manifest_yaml = (
        "id: pasted-python\n"
        "name: Pasted Python Guidelines\n"
        "version: 1.0.0\n"
        "description: PEP 8 guidelines\n"
        "tags: [python, pep8]\n"
    )
    instructions = "# Python Guidelines\nUse type hints everywhere."

    bundle = skill_importer.import_from_paste(
        manifest_yaml=manifest_yaml,
        instructions=instructions,
        enable_immediately=False,
    )

    assert bundle.manifest.id == "pasted-python"
    assert bundle.is_enabled is False
    assert "type hints" in bundle.instructions


def test_sanitize_markdown():
    raw_markdown = (
        "# Title\n\n"
        "<script>alert('xss');</script>\n"
        "Click <a href=\"#\" onclick=\"steal()\">here</a>\n"
        "Or visit [bad link](javascript:alert(document.cookie))\n"
        "<iframe src=\"http://malicious.site\"></iframe>\n"
        "Normal safe content here.\n"
    )

    cleaned = GitHubDiscoveryService.sanitize_markdown(raw_markdown)

    assert "<script>" not in cleaned
    assert "alert('xss')" not in cleaned
    assert "<iframe>" not in cleaned
    assert "onclick" not in cleaned
    assert "javascript:" not in cleaned
    assert "Normal safe content here." in cleaned


def test_api_import_endpoints(tmp_path: Path):
    app = create_app()
    client = TestClient(app)

    # Test paste import endpoint
    resp = client.post(
        "/api/skills/import/paste",
        json={
            "manifest_yaml": "id: api-skill\nname: API Skill\nversion: 1.0.0\ndescription: API test\n",
            "instructions": "Follow secure API guidelines.",
            "enable_immediately": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["manifest"]["id"] == "api-skill"
    assert data["is_enabled"] is False

    # Test invalid folder import endpoint
    resp_bad = client.post(
        "/api/skills/import/folder",
        json={"folder_path": str(tmp_path / "does_not_exist"), "enable_immediately": False},
    )
    assert resp_bad.status_code == 400
