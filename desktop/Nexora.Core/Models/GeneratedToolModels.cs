using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public class TestCaseDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("inputs")]
    public Dictionary<string, object?> Inputs { get; set; } = new();

    [JsonPropertyName("expected_output")]
    public object? ExpectedOutput { get; set; }

    [JsonPropertyName("is_negative")]
    public bool IsNegative { get; set; }
}

public class GeneratedToolManifestDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("version")]
    public string Version { get; set; } = "1.0.0";

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("input_schema")]
    public Dictionary<string, object?> InputSchema { get; set; } = new();

    [JsonPropertyName("output_schema")]
    public Dictionary<string, object?> OutputSchema { get; set; } = new();

    [JsonPropertyName("test_cases")]
    public List<TestCaseDto> TestCases { get; set; } = new();

    [JsonPropertyName("source_sha256")]
    public string SourceSha256 { get; set; } = string.Empty;

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;
}

public class GeneratedToolProposalDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("code")]
    public string Code { get; set; } = string.Empty;

    [JsonPropertyName("input_schema")]
    public Dictionary<string, object?> InputSchema { get; set; } = new();

    [JsonPropertyName("output_schema")]
    public Dictionary<string, object?> OutputSchema { get; set; } = new();

    [JsonPropertyName("test_cases")]
    public List<TestCaseDto> TestCases { get; set; } = new();

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }
}

public class SandboxRunResultDto
{
    [JsonPropertyName("run_id")]
    public string RunId { get; set; } = string.Empty;

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("tool_name")]
    public string ToolName { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("exit_code")]
    public int ExitCode { get; set; }

    [JsonPropertyName("execution_time_ms")]
    public double ExecutionTimeMs { get; set; }

    [JsonPropertyName("peak_memory_bytes")]
    public long PeakMemoryBytes { get; set; }

    [JsonPropertyName("test_results")]
    public List<Dictionary<string, object?>> TestResults { get; set; } = new();

    [JsonPropertyName("output")]
    public object? Output { get; set; }

    [JsonPropertyName("stdout")]
    public string Stdout { get; set; } = string.Empty;

    [JsonPropertyName("stderr")]
    public string Stderr { get; set; } = string.Empty;

    [JsonPropertyName("source_sha256")]
    public string SourceSha256 { get; set; } = string.Empty;

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = string.Empty;
}

public class GeneratedToolRecordDto
{
    [JsonPropertyName("manifest")]
    public GeneratedToolManifestDto Manifest { get; set; } = new();

    [JsonPropertyName("code")]
    public string Code { get; set; } = string.Empty;

    [JsonPropertyName("is_enabled")]
    public bool IsEnabled { get; set; } = true;

    [JsonPropertyName("audit_history")]
    public List<Dictionary<string, object?>> AuditHistory { get; set; } = new();
}

public class ToolValidationReportDto
{
    [JsonPropertyName("is_valid")]
    public bool IsValid { get; set; }

    [JsonPropertyName("errors")]
    public List<string> Errors { get; set; } = new();

    [JsonPropertyName("warnings")]
    public List<string> Warnings { get; set; } = new();

    [JsonPropertyName("source_sha256")]
    public string SourceSha256 { get; set; } = string.Empty;
}

public class TrialRunRequestDto
{
    [JsonPropertyName("proposal")]
    public GeneratedToolProposalDto Proposal { get; set; } = new();

    [JsonPropertyName("mode")]
    public string Mode { get; set; } = "test";

    [JsonPropertyName("runtime_arguments")]
    public Dictionary<string, object?>? RuntimeArguments { get; set; }
}

public class ToolPromotionRequestDto
{
    [JsonPropertyName("proposal")]
    public GeneratedToolProposalDto Proposal { get; set; } = new();

    [JsonPropertyName("evidence_run_id")]
    public string EvidenceRunId { get; set; } = string.Empty;

    [JsonPropertyName("reviewer")]
    public string Reviewer { get; set; } = "operator";
}

public class ToolUpdateRequestDto
{
    [JsonPropertyName("is_enabled")]
    public bool? IsEnabled { get; set; }

    [JsonPropertyName("target_version")]
    public string? TargetVersion { get; set; }
}
