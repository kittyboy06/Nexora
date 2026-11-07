"""Curated Specialist Catalog for Dynamic Agent Fleet."""

from pydantic import BaseModel, ConfigDict, Field


class SpecialistProfile(BaseModel):
    """Verified specification for a specialist agent role."""

    model_config = ConfigDict(frozen=True)

    role_id: str
    display_name: str
    description: str
    system_prompt_template: str
    capability_allowlist: list[str] = Field(default_factory=list)
    default_token_budget: int = 2048
    recommended_model_tier: str = "general"


DEFAULT_SPECIALIST_PROFILES: dict[str, SpecialistProfile] = {
    "planner": SpecialistProfile(
        role_id="planner",
        display_name="Fleet Planner",
        description="Analyzes complex goals and formulates a validated FleetPlan DAG of subtasks.",
        system_prompt_template=(
            "You are the NEXORA Fleet Planner. Your responsibility is to analyze the user goal, "
            "break it down into bounded specialist subtasks, and produce a structured FleetPlan DAG. "
            "You have no tool execution capabilities. Focus on rigorous decomposition, dependency ordering, "
            "and scoping each node to a clear, achievable objective."
        ),
        capability_allowlist=[],
        default_token_budget=2048,
        recommended_model_tier="general",
    ),
    "researcher": SpecialistProfile(
        role_id="researcher",
        display_name="System & Codebase Researcher",
        description="Inspects directories, reads files, and analyzes repository state to gather factual evidence.",
        system_prompt_template=(
            "You are the NEXORA Codebase and System Researcher. Your role is to inspect the workspace, "
            "locate relevant source files, read configurations, and summarize factual evidence for downstream specialists. "
            "You may inspect and read files, but you cannot modify any state or execute commands."
        ),
        capability_allowlist=["list_directory", "read_file", "search_files"],
        default_token_budget=2048,
        recommended_model_tier="general",
    ),
    "coder": SpecialistProfile(
        role_id="coder",
        display_name="Software Engineer",
        description="Implements code changes, creates new files, and tests builds within approved boundaries.",
        system_prompt_template=(
            "You are the NEXORA Software Engineer. Your role is to implement validated code changes, "
            "create or edit files, and run build commands based strictly on the input artifacts and your subtask objective. "
            "Do not execute commands or modify files outside your explicit subtask objective."
        ),
        capability_allowlist=["read_file", "write_file", "execute_command"],
        default_token_budget=4096,
        recommended_model_tier="coder",
    ),
    "auditor_verifier": SpecialistProfile(
        role_id="auditor_verifier",
        display_name="Quality & Verification Auditor",
        description="Validates postconditions, tests code syntax and unit tests, and verifies evidence records.",
        system_prompt_template=(
            "You are the NEXORA Quality & Verification Auditor. Your role is to review code, run test suites, "
            "and verify that the objective's postconditions are met. Verify factual test output and report "
            "whether the implementation passes all quality gates without claiming unverified outcomes."
        ),
        capability_allowlist=["read_file", "execute_command"],
        default_token_budget=2048,
        recommended_model_tier="general",
    ),
}


class SpecialistCatalog:
    """Registry maintaining curated specialist profiles."""

    def __init__(self, profiles: dict[str, SpecialistProfile] | None = None) -> None:
        self._profiles: dict[str, SpecialistProfile] = dict(profiles or DEFAULT_SPECIALIST_PROFILES)

    def get(self, role_id: str) -> SpecialistProfile | None:
        """Lookup a specialist profile by role ID."""
        return self._profiles.get(role_id)

    def list_profiles(self) -> list[SpecialistProfile]:
        """Return all available specialist profiles."""
        return list(self._profiles.values())

    def validate_capabilities(self, role_id: str, requested_capabilities: list[str]) -> bool:
        """Verify that all requested capabilities are within the specialist's locked allowlist."""
        profile = self.get(role_id)
        if not profile:
            return False
        return all(cap in profile.capability_allowlist for cap in requested_capabilities)

    def register_custom(self, profile: SpecialistProfile) -> None:
        """Register or override a specialist profile."""
        self._profiles[profile.role_id] = profile
