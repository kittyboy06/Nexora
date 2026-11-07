"""Unit tests for SkillManager, models, and disk storage."""

import hashlib
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.app.skills.manager import SkillManager
from backend.app.skills.models import (
    SkillBundle,
    SkillManifest,
    SkillPatchRequest,
    SkillProvenance,
)


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Provide an isolated temporary directory for skills."""
    d = tmp_path / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def manager(skills_dir: Path) -> SkillManager:
    """Return a clean SkillManager instance backed by temporary storage."""
    return SkillManager(base_dir=skills_dir)


def test_manifest_validation():
    """Verify regex and length constraints on SkillManifest."""
    # Valid manifest
    m = SkillManifest(
        id="docker-expert",
        name="Docker Expert",
        version="1.0.0",
        description="Best practices for writing Dockerfiles and Compose files.",
        tags=["docker", "containers"],
        target_roles=["coder"],
    )
    assert m.id == "docker-expert"
    assert m.version == "1.0.0"

    # Invalid ID with uppercase and spaces
    with pytest.raises(ValidationError):
        SkillManifest(
            id="Docker Expert!",
            name="Docker Expert",
            version="1.0.0",
            description="desc",
        )

    # Invalid version
    with pytest.raises(ValidationError):
        SkillManifest(
            id="docker-expert",
            name="Docker Expert",
            version="v1.0",
            description="desc",
        )

    # Oversized description (>500 chars)
    with pytest.raises(ValidationError):
        SkillManifest(
            id="docker-expert",
            name="Docker Expert",
            version="1.0.0",
            description="A" * 501,
        )


def test_manager_empty_init(manager: SkillManager, skills_dir: Path):
    """Verify empty directory initialization and empty catalog list."""
    assert (skills_dir / "registry.json").exists()
    assert manager.list_skills() == []


def test_install_and_get_bundle(manager: SkillManager, skills_dir: Path):
    """Verify installing a skill writes all bundle files and can be fetched."""
    manifest = SkillManifest(
        id="git-pro",
        name="Git Pro",
        version="1.0.0",
        description="Comprehensive Git workflows.",
        tags=["git", "vcs"],
        target_roles=["coder"],
    )
    instructions = "# Git Workflows\n\nAlways use conventional commits."

    bundle = manager.install_bundle(manifest, instructions)
    assert bundle.manifest.id == "git-pro"
    assert bundle.manifest.version == "1.0.0"
    assert bundle.is_enabled is True
    assert bundle.is_active_version is True
    assert bundle.is_valid is True

    # Check files on disk
    bundle_dir = skills_dir / "git-pro" / "1.0.0"
    assert (bundle_dir / "manifest.json").exists()
    assert (bundle_dir / "SKILL.md").exists()
    assert (bundle_dir / "provenance.json").exists()

    expected_hash = hashlib.sha256(instructions.encode("utf-8")).hexdigest()
    assert bundle.provenance.skill_sha256 == expected_hash

    # Verify retrieval
    retrieved = manager.get_skill("git-pro")
    assert retrieved is not None
    assert retrieved.instructions == instructions
    assert retrieved.manifest.name == "Git Pro"


def test_multi_version_coexistence(manager: SkillManager):
    """Verify multiple versions of the same skill can be stored and queried."""
    m1 = SkillManifest(
        id="python-expert",
        name="Python Expert",
        version="1.0.0",
        description="Python 3.10 guidance.",
    )
    m2 = SkillManifest(
        id="python-expert",
        name="Python Expert",
        version="2.0.0",
        description="Python 3.14 async guidance.",
    )

    manager.install_bundle(m1, "# Python 1.0 Instructions", set_active=False)
    manager.install_bundle(m2, "# Python 2.0 Instructions", set_active=True)

    # Default get_skill returns active version (2.0.0)
    active = manager.get_skill("python-expert")
    assert active is not None
    assert active.manifest.version == "2.0.0"
    assert active.is_active_version is True

    # Explicit version lookup
    v1 = manager.get_skill("python-expert", version="1.0.0")
    assert v1 is not None
    assert v1.manifest.version == "1.0.0"
    assert v1.is_active_version is False

    # List all versions
    all_versions = manager.list_skill_versions("python-expert")
    assert len(all_versions) == 2


def test_patch_skill_toggle_and_active_version(manager: SkillManager):
    """Verify toggling enabled state and switching active versions."""
    m1 = SkillManifest(
        id="security-audit",
        name="Security Audit",
        version="1.0.0",
        description="Basic security review.",
    )
    m2 = SkillManifest(
        id="security-audit",
        name="Security Audit",
        version="1.1.0",
        description="Advanced security review.",
    )

    manager.install_bundle(m1, "Review step 1")
    manager.install_bundle(m2, "Review step 2", set_active=True)

    # Toggle off
    manager.patch_skill("security-audit", SkillPatchRequest(is_enabled=False))
    bundle = manager.get_skill("security-audit")
    assert bundle.is_enabled is False

    # Ensure list_skills(enabled_only=True) filters it out
    assert len(manager.list_skills(enabled_only=True)) == 0
    assert len(manager.list_skills(enabled_only=False)) == 1

    # Switch active version to 1.0.0
    manager.patch_skill(
        "security-audit",
        SkillPatchRequest(is_enabled=True, active_version="1.0.0"),
    )
    active = manager.get_skill("security-audit")
    assert active.is_enabled is True
    assert active.manifest.version == "1.0.0"

    # Error if switching to non-existent version
    with pytest.raises(ValueError):
        manager.patch_skill(
            "security-audit",
            SkillPatchRequest(active_version="9.9.9"),
        )


def test_delete_skill(manager: SkillManager, skills_dir: Path):
    """Verify deleting a specific version and deleting the whole skill."""
    m1 = SkillManifest(id="temp-skill", name="Temp", version="1.0.0", description="v1")
    m2 = SkillManifest(id="temp-skill", name="Temp", version="2.0.0", description="v2")

    manager.install_bundle(m1, "v1 instructions")
    manager.install_bundle(m2, "v2 instructions", set_active=True)

    # Delete version 2.0.0
    assert manager.delete_skill("temp-skill", version="2.0.0") is True
    assert (skills_dir / "temp-skill" / "2.0.0").exists() is False
    assert (skills_dir / "temp-skill" / "1.0.0").exists() is True

    # 1.0.0 should now be active
    remaining = manager.get_skill("temp-skill")
    assert remaining is not None
    assert remaining.manifest.version == "1.0.0"

    # Delete entire skill
    assert manager.delete_skill("temp-skill") is True
    assert (skills_dir / "temp-skill").exists() is False
    assert manager.get_skill("temp-skill") is None


def test_corrupted_instructions_hash_mismatch(manager: SkillManager, skills_dir: Path):
    """Verify external file tampering triggers SHA-256 integrity failure."""
    m = SkillManifest(id="tamper-test", name="Tamper", version="1.0.0", description="d")
    manager.install_bundle(m, "Original instructions")

    # Tamper with SKILL.md directly on disk
    skill_file = skills_dir / "tamper-test" / "1.0.0" / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write("Tampered malicious instructions!")

    # Verify integrity method detects it
    valid, err = manager.verify_integrity("tamper-test")
    assert valid is False
    assert "Hash mismatch" in err

    # Reload manager: bundle should be marked invalid
    manager.reload()
    bundle = manager.get_skill("tamper-test")
    assert bundle is not None
    assert bundle.is_valid is False
    assert "SHA-256 hash mismatch" in bundle.validation_error


def test_role_filtering(manager: SkillManager):
    """Verify filtering skills by target role."""
    m_coder = SkillManifest(
        id="coder-skill",
        name="Coder Skill",
        version="1.0.0",
        description="c",
        target_roles=["coder"],
    )
    m_researcher = SkillManifest(
        id="researcher-skill",
        name="Researcher Skill",
        version="1.0.0",
        description="r",
        target_roles=["researcher"],
    )
    m_general = SkillManifest(
        id="general-skill",
        name="General Skill",
        version="1.0.0",
        description="g",
        target_roles=[],
    )

    manager.install_bundle(m_coder, "coder guidance")
    manager.install_bundle(m_researcher, "researcher guidance")
    manager.install_bundle(m_general, "general guidance")

    coder_skills = manager.list_skills(role="coder")
    coder_ids = [s.id for s in coder_skills]
    assert "coder-skill" in coder_ids
    assert "general-skill" in coder_ids
    assert "researcher-skill" not in coder_ids
