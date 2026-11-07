using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum TaskStatus
{
    SUBMITTED,
    PARSING,
    PLANNING,
    EXECUTING,
    WAITING_APPROVAL,
    APPROVED,
    REJECTED,
    EXPIRED,
    COMPLETED,
    FAILED,
    CANCELLED,
    INTERRUPTED
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum StepStatus
{
    PENDING,
    RUNNING,
    SUCCEEDED,
    FAILED,
    SKIPPED
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum RiskLevel
{
    SAFE,
    CONTROLLED,
    SENSITIVE
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum RetryClassification
{
    TRANSIENT,
    PERMANENT,
    UNCERTAIN
}

public record RouteSelection(
    [property: JsonPropertyName("profile_id")] string ProfileId,
    [property: JsonPropertyName("model")] string Model,
    [property: JsonPropertyName("task_kind")] string TaskKind,
    [property: JsonPropertyName("reason")] string Reason,
    [property: JsonPropertyName("escalated")] bool Escalated = false
);

public record ToolCall(
    [property: JsonPropertyName("tool_name")] string ToolName,
    [property: JsonPropertyName("arguments")] Dictionary<string, object?> Arguments
);

public record PlanStep(
    [property: JsonPropertyName("step_id")] int StepId,
    [property: JsonPropertyName("description")] string Description,
    [property: JsonPropertyName("tool_call")] ToolCall ToolCall,
    [property: JsonPropertyName("dependencies")] List<int> Dependencies,
    [property: JsonPropertyName("risk_level")] RiskLevel RiskLevel = RiskLevel.SAFE,
    [property: JsonPropertyName("status")] StepStatus Status = StepStatus.PENDING,
    [property: JsonPropertyName("retries_attempted")] int RetriesAttempted = 0
);

public record TaskPlan(
    [property: JsonPropertyName("plan_id")] string PlanId,
    [property: JsonPropertyName("goal")] string Goal,
    [property: JsonPropertyName("steps")] List<PlanStep> Steps,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt
);

public record StepResult(
    [property: JsonPropertyName("step_id")] int StepId,
    [property: JsonPropertyName("tool_name")] string ToolName,
    [property: JsonPropertyName("status")] StepStatus Status,
    [property: JsonPropertyName("output")] object? Output = null,
    [property: JsonPropertyName("error")] string? Error = null,
    [property: JsonPropertyName("duration_ms")] double DurationMs = 0.0,
    [property: JsonPropertyName("retry_classification")] RetryClassification? RetryClassification = null
);

public record AgentTask(
    [property: JsonPropertyName("task_id")] string TaskId,
    [property: JsonPropertyName("prompt")] string Prompt,
    [property: JsonPropertyName("model_profile_id")] string? ModelProfileId = null,
    [property: JsonPropertyName("status")] TaskStatus Status = TaskStatus.SUBMITTED,
    [property: JsonPropertyName("routing")] RouteSelection? Routing = null,
    [property: JsonPropertyName("plan")] TaskPlan? Plan = null,
    [property: JsonPropertyName("execution_trace")] List<StepResult>? ExecutionTrace = null,
    [property: JsonPropertyName("pending_approval")] ActionApproval? PendingApproval = null,
    [property: JsonPropertyName("iterations_used")] int IterationsUsed = 0,
    [property: JsonPropertyName("created_at")] DateTimeOffset? CreatedAt = null,
    [property: JsonPropertyName("updated_at")] DateTimeOffset? UpdatedAt = null,
    [property: JsonPropertyName("completed_at")] DateTimeOffset? CompletedAt = null,
    [property: JsonPropertyName("error_message")] string? ErrorMessage = null
);

public record TaskCreateRequest(
    [property: JsonPropertyName("prompt")] string Prompt,
    [property: JsonPropertyName("model_profile_id")] string? ModelProfileId = null
);

public record TaskResponse(
    [property: JsonPropertyName("task")] AgentTask Task
);

public record TaskListResponse(
    [property: JsonPropertyName("tasks")] List<AgentTask> Tasks,
    [property: JsonPropertyName("count")] int Count
);
