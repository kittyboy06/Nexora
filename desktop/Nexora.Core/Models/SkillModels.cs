using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public class SkillManifestDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("version")]
    public string Version { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("tags")]
    public List<string> Tags { get; set; } = new();

    [JsonPropertyName("author")]
    public string Author { get; set; } = string.Empty;

    [JsonPropertyName("license")]
    public string License { get; set; } = "MIT";

    [JsonPropertyName("target_roles")]
    public List<string> TargetRoles { get; set; } = new();

    [JsonPropertyName("required_tools")]
    public List<string> RequiredTools { get; set; } = new();

    [JsonPropertyName("category")]
    public string Category { get; set; } = "general";
}

public class SkillProvenanceDto
{
    [JsonPropertyName("source_url")]
    public string SourceUrl { get; set; } = string.Empty;

    [JsonPropertyName("commit_sha")]
    public string? CommitSha { get; set; }

    [JsonPropertyName("installed_at")]
    public string InstalledAt { get; set; } = string.Empty;

    [JsonPropertyName("skill_sha256")]
    public string SkillSha256 { get; set; } = string.Empty;

    [JsonPropertyName("reviewer")]
    public string Reviewer { get; set; } = "operator";
}

public class SkillBundleDto
{
    [JsonPropertyName("manifest")]
    public SkillManifestDto Manifest { get; set; } = new();

    [JsonPropertyName("provenance")]
    public SkillProvenanceDto Provenance { get; set; } = new();

    [JsonPropertyName("instructions")]
    public string Instructions { get; set; } = string.Empty;

    [JsonPropertyName("is_enabled")]
    public bool IsEnabled { get; set; } = true;

    [JsonPropertyName("is_active_version")]
    public bool IsActiveVersion { get; set; } = true;

    [JsonPropertyName("is_valid")]
    public bool IsValid { get; set; } = true;

    [JsonPropertyName("validation_error")]
    public string? ValidationError { get; set; }
}

public class SkillSummaryDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("version")]
    public string Version { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("tags")]
    public List<string> Tags { get; set; } = new();

    [JsonPropertyName("target_roles")]
    public List<string> TargetRoles { get; set; } = new();

    [JsonPropertyName("author")]
    public string Author { get; set; } = string.Empty;

    [JsonPropertyName("license")]
    public string License { get; set; } = "MIT";

    [JsonPropertyName("category")]
    public string Category { get; set; } = "general";

    [JsonPropertyName("is_enabled")]
    public bool IsEnabled { get; set; } = true;

    [JsonPropertyName("is_active_version")]
    public bool IsActiveVersion { get; set; } = true;

    [JsonPropertyName("is_valid")]
    public bool IsValid { get; set; } = true;

    [JsonPropertyName("skill_sha256")]
    public string SkillSha256 { get; set; } = string.Empty;

    [JsonPropertyName("installed_at")]
    public string InstalledAt { get; set; } = string.Empty;
}

public class InstallSkillRequestDto
{
    [JsonPropertyName("owner")]
    public string? Owner { get; set; }

    [JsonPropertyName("repo")]
    public string? Repo { get; set; }

    [JsonPropertyName("branch")]
    public string? Branch { get; set; } = "main";

    [JsonPropertyName("path")]
    public string? Path { get; set; }

    [JsonPropertyName("manifest")]
    public SkillManifestDto? Manifest { get; set; }

    [JsonPropertyName("instructions")]
    public string? Instructions { get; set; }

    [JsonPropertyName("source_url")]
    public string? SourceUrl { get; set; }
}

public class SkillDiscoveryCandidateDto
{
    [JsonPropertyName("owner")]
    public string Owner { get; set; } = string.Empty;

    [JsonPropertyName("repo")]
    public string Repo { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("stars")]
    public int Stars { get; set; }

    [JsonPropertyName("html_url")]
    public string HtmlUrl { get; set; } = string.Empty;

    [JsonPropertyName("default_branch")]
    public string DefaultBranch { get; set; } = "main";

    [JsonPropertyName("has_skill_md")]
    public bool HasSkillMd { get; set; }

    [JsonPropertyName("has_manifest")]
    public bool HasManifest { get; set; }

    [JsonPropertyName("manifest_preview")]
    public SkillManifestDto? ManifestPreview { get; set; }

    [JsonPropertyName("skill_md_preview")]
    public string? SkillMdPreview { get; set; }
}

public class GitHubRateLimitStatusDto
{
    [JsonPropertyName("limit")]
    public int Limit { get; set; } = 60;

    [JsonPropertyName("remaining")]
    public int Remaining { get; set; } = 60;

    [JsonPropertyName("reset_at")]
    public string? ResetAt { get; set; }

    [JsonPropertyName("is_authenticated")]
    public bool IsAuthenticated { get; set; }
}

public class SkillImportFolderRequestDto
{
    [JsonPropertyName("folder_path")]
    public string FolderPath { get; set; } = string.Empty;

    [JsonPropertyName("enable_immediately")]
    public bool EnableImmediately { get; set; }
}

public class SkillImportPasteRequestDto
{
    [JsonPropertyName("manifest_yaml")]
    public string ManifestYaml { get; set; } = string.Empty;

    [JsonPropertyName("instructions")]
    public string Instructions { get; set; } = string.Empty;

    [JsonPropertyName("enable_immediately")]
    public bool EnableImmediately { get; set; }

    [JsonPropertyName("source_note")]
    public string? SourceNote { get; set; } = "pasted";
}

public class SkillReadmePreviewResponseDto
{
    [JsonPropertyName("owner")]
    public string Owner { get; set; } = string.Empty;

    [JsonPropertyName("repo")]
    public string Repo { get; set; } = string.Empty;

    [JsonPropertyName("branch")]
    public string Branch { get; set; } = "main";

    [JsonPropertyName("sanitized_markdown")]
    public string SanitizedMarkdown { get; set; } = string.Empty;

    [JsonPropertyName("length")]
    public int Length { get; set; }
}
