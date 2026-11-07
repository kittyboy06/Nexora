"""Unit tests for SpecialistCatalog and SpecialistProfile."""

from backend.app.agent.fleet.catalog import SpecialistCatalog, SpecialistProfile


def test_default_profiles_exist():
    catalog = SpecialistCatalog()
    profiles = catalog.list_profiles()
    assert len(profiles) >= 4

    role_ids = {p.role_id for p in profiles}
    assert {"planner", "researcher", "coder", "auditor_verifier"}.issubset(role_ids)


def test_catalog_profile_lookup():
    catalog = SpecialistCatalog()
    planner = catalog.get("planner")
    assert planner is not None
    assert planner.capability_allowlist == []

    researcher = catalog.get("researcher")
    assert researcher is not None
    assert "read_file" in researcher.capability_allowlist
    assert "write_file" not in researcher.capability_allowlist

    coder = catalog.get("coder")
    assert coder is not None
    assert "write_file" in coder.capability_allowlist
    assert coder.default_token_budget == 4096


def test_validate_capabilities():
    catalog = SpecialistCatalog()
    # Researcher cannot write_file
    assert catalog.validate_capabilities("researcher", ["read_file", "list_directory"]) is True
    assert catalog.validate_capabilities("researcher", ["read_file", "write_file"]) is False

    # Unknown role
    assert catalog.validate_capabilities("nonexistent_role", ["read_file"]) is False


def test_custom_profile_registration():
    catalog = SpecialistCatalog()
    custom = SpecialistProfile(
        role_id="custom_specialist",
        display_name="Custom Specialist",
        description="A custom specialist",
        system_prompt_template="Custom template",
        capability_allowlist=["custom_tool"],
    )
    catalog.register_custom(custom)
    assert catalog.get("custom_specialist") == custom
    assert catalog.validate_capabilities("custom_specialist", ["custom_tool"]) is True
