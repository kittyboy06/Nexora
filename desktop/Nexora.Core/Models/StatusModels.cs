using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public record HealthResponse(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("version")] string Version,
    [property: JsonPropertyName("ollama_configured")] bool OllamaConfigured = true,
    [property: JsonPropertyName("active_task_id")] string? ActiveTaskId = null,
    [property: JsonPropertyName("timestamp")] DateTimeOffset? Timestamp = null
);

public record OllamaStatusResponse(
    [property: JsonPropertyName("reachable")] bool Reachable,
    [property: JsonPropertyName("model_available")] bool ModelAvailable,
    [property: JsonPropertyName("configured_model")] string ConfiguredModel,
    [property: JsonPropertyName("installed_models")] List<string>? InstalledModels = null,
    [property: JsonPropertyName("checked_at")] DateTimeOffset? CheckedAt = null
);

public record ModelProfileStatus(
    [property: JsonPropertyName("profile_id")] string ProfileId,
    [property: JsonPropertyName("model")] string Model,
    [property: JsonPropertyName("specialties")] List<string> Specialties,
    [property: JsonPropertyName("system_instruction")] string SystemInstruction = "",
    [property: JsonPropertyName("role")] string Role = "planner",
    [property: JsonPropertyName("enabled")] bool Enabled = true,
    [property: JsonPropertyName("installed")] bool Installed = false
);

public record ModelProfileListResponse(
    [property: JsonPropertyName("profiles")] List<ModelProfileStatus> Profiles,
    [property: JsonPropertyName("count")] int Count
);

public record ErrorDetail(
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("details")] object? Details = null
);

public record ErrorResponse(
    [property: JsonPropertyName("error")] ErrorDetail Error
);

public record SetActiveModelRequest(
    [property: JsonPropertyName("model")] string Model
);

public record SetActiveModelResponse(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("active_model")] string ActiveModel
);

public enum AppThemeMode
{
    SystemDefault = 0,
    Light = 1,
    Dark = 2
}
