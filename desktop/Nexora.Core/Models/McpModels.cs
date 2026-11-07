using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public class McpServerConfigDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("transport")]
    public string Transport { get; set; } = "stdio";

    [JsonPropertyName("command")]
    public string Command { get; set; } = string.Empty;

    [JsonPropertyName("args")]
    public List<string> Args { get; set; } = new();

    [JsonPropertyName("env")]
    public Dictionary<string, string> Env { get; set; } = new();

    [JsonPropertyName("working_dir")]
    public string? WorkingDir { get; set; }

    [JsonPropertyName("is_approved")]
    public bool IsApproved { get; set; }

    [JsonPropertyName("is_enabled")]
    public bool IsEnabled { get; set; } = true;
}

public class McpToolDefinitionDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("input_schema")]
    public Dictionary<string, object> InputSchema { get; set; } = new();

    [JsonPropertyName("risk_level")]
    public string RiskLevel { get; set; } = "CONTROLLED";
}

public class McpServerRecordDto
{
    [JsonPropertyName("config")]
    public McpServerConfigDto Config { get; set; } = new();

    [JsonPropertyName("status")]
    public string Status { get; set; } = "DISCOVERED";

    [JsonPropertyName("advertised_tools")]
    public List<McpToolDefinitionDto> AdvertisedTools { get; set; } = new();

    [JsonPropertyName("protocol_version")]
    public string? ProtocolVersion { get; set; }

    [JsonPropertyName("last_connected_at")]
    public string? LastConnectedAt { get; set; }

    [JsonPropertyName("last_error")]
    public string? LastError { get; set; }

    [JsonPropertyName("ping_latency_ms")]
    public double? PingLatencyMs { get; set; }
}

public class McpVaultItemSummaryDto
{
    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;

    [JsonPropertyName("has_value")]
    public bool HasValue { get; set; } = true;
}

public class McpVaultWriteRequestDto
{
    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;

    [JsonPropertyName("secret_value")]
    public string SecretValue { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;
}

public class McpServerCreateRequestDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("command")]
    public string Command { get; set; } = string.Empty;

    [JsonPropertyName("args")]
    public List<string> Args { get; set; } = new();

    [JsonPropertyName("env")]
    public Dictionary<string, string> Env { get; set; } = new();

    [JsonPropertyName("working_dir")]
    public string? WorkingDir { get; set; }
}

public class McpServerUpdateRequestDto
{
    [JsonPropertyName("name")]
    public string? Name { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("command")]
    public string? Command { get; set; }

    [JsonPropertyName("args")]
    public List<string>? Args { get; set; }

    [JsonPropertyName("env")]
    public Dictionary<string, string>? Env { get; set; }

    [JsonPropertyName("working_dir")]
    public string? WorkingDir { get; set; }

    [JsonPropertyName("is_enabled")]
    public bool? IsEnabled { get; set; }
}

public class McpPingResponseDto
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("latency_ms")]
    public double LatencyMs { get; set; }
}
