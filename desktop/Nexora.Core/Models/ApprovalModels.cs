using System;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public record ActionApproval(
    [property: JsonPropertyName("approval_id")] string ApprovalId,
    [property: JsonPropertyName("task_id")] string TaskId,
    [property: JsonPropertyName("step_id")] int StepId,
    [property: JsonPropertyName("tool_name")] string ToolName,
    [property: JsonPropertyName("argument_hash")] string ArgumentHash,
    [property: JsonPropertyName("expires_at")] DateTimeOffset ExpiresAt,
    [property: JsonPropertyName("created_at")] DateTimeOffset? CreatedAt = null
);

public record ApprovalDecisionRequest(
    [property: JsonPropertyName("approval_id")] string ApprovalId,
    [property: JsonPropertyName("approved")] bool Approved
);
