"""Domain models for Phase 7: Skills and GitHub Discovery."""

from datetime import datetime, timezone
import hashlib
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class SkillManifest(BaseModel):
    """Declarative specification for an operational guidance skill."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        ...,
        pattern=r"^[a-z0-9\-_]+$",
        min_length=1,
        max_length=64,
        description="Unique URL-friendly slug identifier for the skill",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version string (e.g. 1.0.0)",
    )
    description: str = Field(..., max_length=500, description="Summary of skill guidance")
    tags: list[str] = Field(default_factory=list, description="Categorization keywords")
    author: str = Field(default="", max_length=100, description="Author or maintainer handle")
    license: str = Field(default="MIT", max_length=50, description="License type")
    target_roles: list[str] = Field(
        default_factory=list,
        description="Compatible agent roles (e.g. planner, coder, researcher, auditor_verifier)",
    )
    required_tools: list[str] = Field(
        default_factory=list,
        description="Tools informational requirements (skills cannot grant permissions)",
    )
    category: str = Field(default="general", max_length=50, description="Skill domain category")


class SkillProvenance(BaseModel):
    """Cryptographic and audit provenance record for an installed skill."""

    model_config = ConfigDict(extra="ignore")

    source_url: str = Field(..., description="Source repository URL or local import path")
    commit_sha: Optional[str] = Field(default=None, description="Source Git commit SHA if known")
    installed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC installation timestamp",
    )
    skill_sha256: str = Field(..., description="SHA-256 hash of the SKILL.md instruction body")
    reviewer: str = Field(default="operator", description="Reviewer or operator identity")


class SkillBundle(BaseModel):
    """In-memory representation of a validated skill bundle on disk."""

    manifest: SkillManifest
    provenance: SkillProvenance
    instructions: str = Field(..., description="Raw Markdown guidance text")
    is_enabled: bool = Field(default=True, description="Whether the skill is enabled by operator")
    is_active_version: bool = Field(
        default=True,
        description="Whether this is the currently active version of the skill",
    )
    is_valid: bool = Field(default=True, description="Whether the bundle is structurally sound")
    validation_error: Optional[str] = Field(
        default=None,
        description="Explanation if bundle failed validation",
    )


class SkillSummary(BaseModel):
    """Lightweight projection of a skill bundle for catalog listing."""

    id: str
    name: str
    version: str
    description: str
    tags: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    author: str = ""
    license: str = "MIT"
    category: str = "general"
    is_enabled: bool = True
    is_active_version: bool = True
    is_valid: bool = True
    skill_sha256: str
    installed_at: str

    @classmethod
    def from_bundle(cls, bundle: SkillBundle) -> "SkillSummary":
        return cls(
            id=bundle.manifest.id,
            name=bundle.manifest.name,
            version=bundle.manifest.version,
            description=bundle.manifest.description,
            tags=bundle.manifest.tags,
            target_roles=bundle.manifest.target_roles,
            author=bundle.manifest.author,
            license=bundle.manifest.license,
            category=bundle.manifest.category,
            is_enabled=bundle.is_enabled,
            is_active_version=bundle.is_active_version,
            is_valid=bundle.is_valid,
            skill_sha256=bundle.provenance.skill_sha256,
            installed_at=bundle.provenance.installed_at,
        )


class SkillPatchRequest(BaseModel):
    """Payload to toggle skill enabled status or switch active version."""

    is_enabled: Optional[bool] = None
    active_version: Optional[str] = None


class InstallSkillRequest(BaseModel):
    """Request payload to install a skill either from GitHub discovery or direct definition."""

    owner: Optional[str] = None
    repo: Optional[str] = None
    branch: Optional[str] = "main"
    path: Optional[str] = None
    manifest: Optional[SkillManifest] = None
    instructions: Optional[str] = None
    source_url: Optional[str] = None


class SkillDiscoveryCandidate(BaseModel):
    """Repository search hit from GitHub discovery."""

    owner: str
    repo: str
    description: Optional[str] = None
    stars: int = 0
    html_url: str
    default_branch: str = "main"
    has_skill_md: bool = False
    has_manifest: bool = False
    manifest_preview: Optional[SkillManifest] = None
    skill_md_preview: Optional[str] = None


class GitHubRateLimitStatus(BaseModel):
    """Remaining quota tracking for GitHub REST API."""

    limit: int = 60
    remaining: int = 60
    reset_at: Optional[str] = None
    is_authenticated: bool = False


class SkillImportFolderRequest(BaseModel):
    """Payload to import a skill from a local filesystem folder."""

    folder_path: str = Field(..., description="Absolute or relative path to directory containing skill")
    enable_immediately: bool = Field(default=False, description="Whether to enable immediately without review")


class SkillImportPasteRequest(BaseModel):
    """Payload to import a skill directly from YAML/JSON and instructions markdown."""

    manifest_yaml: str = Field(..., description="YAML or JSON skill manifest")
    instructions: str = Field(..., description="Markdown guidance body")
    enable_immediately: bool = Field(default=False, description="Whether to enable immediately without review")
    source_note: Optional[str] = Field(default="pasted", description="Audit note identifying provenance")


class SkillReadmePreviewResponse(BaseModel):
    """Sanitized GitHub repository README preview."""

    owner: str
    repo: str
    branch: str = "main"
    sanitized_markdown: str
    length: int = 0
