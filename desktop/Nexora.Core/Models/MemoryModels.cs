using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public class MemoryRecordDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; set; } = "project_fact";

    [JsonPropertyName("value")]
    public string Value { get; set; } = string.Empty;

    [JsonPropertyName("sensitivity")]
    public string Sensitivity { get; set; } = "MEDIUM";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "ACTIVE";

    [JsonPropertyName("provenance_task_id")]
    public string? ProvenanceTaskId { get; set; }

    [JsonPropertyName("provenance_reason")]
    public string? ProvenanceReason { get; set; }

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;

    [JsonPropertyName("updated_at")]
    public string UpdatedAt { get; set; } = string.Empty;

    [JsonPropertyName("expires_at")]
    public string? ExpiresAt { get; set; }

    [JsonPropertyName("version_hash")]
    public string VersionHash { get; set; } = string.Empty;
}

public class MemoryProposalDto
{
    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; set; } = "project_fact";

    [JsonPropertyName("value")]
    public string Value { get; set; } = string.Empty;

    [JsonPropertyName("sensitivity")]
    public string Sensitivity { get; set; } = "MEDIUM";

    [JsonPropertyName("provenance_task_id")]
    public string? ProvenanceTaskId { get; set; }

    [JsonPropertyName("provenance_reason")]
    public string ProvenanceReason { get; set; } = string.Empty;

    [JsonPropertyName("ttl_days")]
    public int? TtlDays { get; set; }
}

public class MemoryUpdateRequestDto
{
    [JsonPropertyName("value")]
    public string? Value { get; set; }

    [JsonPropertyName("category")]
    public string? Category { get; set; }

    [JsonPropertyName("sensitivity")]
    public string? Sensitivity { get; set; }

    [JsonPropertyName("expires_at")]
    public string? ExpiresAt { get; set; }

    [JsonPropertyName("reason")]
    public string? Reason { get; set; }
}

public class MemoryAuditEntryDto
{
    [JsonPropertyName("id")]
    public int? Id { get; set; }

    [JsonPropertyName("memory_id")]
    public string MemoryId { get; set; } = string.Empty;

    [JsonPropertyName("action")]
    public string Action { get; set; } = string.Empty;

    [JsonPropertyName("actor")]
    public string Actor { get; set; } = "agent";

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("details")]
    public string? Details { get; set; }

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = string.Empty;
}

public class MemoryBackupInfoDto
{
    [JsonPropertyName("backup_path")]
    public string BackupPath { get; set; } = string.Empty;

    [JsonPropertyName("record_count")]
    public int RecordCount { get; set; }

    [JsonPropertyName("file_size_bytes")]
    public long FileSizeBytes { get; set; }

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;

    [JsonPropertyName("is_valid")]
    public bool IsValid { get; set; }
}
