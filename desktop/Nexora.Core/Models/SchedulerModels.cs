using System;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum TriggerType
{
    CRON,
    INTERVAL,
    ONE_SHOT
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum ScheduleStatus
{
    ACTIVE,
    PAUSED,
    PAUSED_INVALIDATED,
    COMPLETED
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum MissedRunPolicy
{
    SKIP_NOTIFY,
    RUN_ONCE_CATCHUP
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum ConcurrencyPolicy
{
    SKIP_BUSY,
    RETRY_GRACE
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum RunStatus
{
    DISPATCHED,
    COMPLETED,
    FAILED,
    SKIPPED,
    BLOCKED_BUSY,
    EXPIRED_APPROVAL,
    INTERRUPTED
}

public class ScheduleDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("prompt_template")]
    public string PromptTemplate { get; set; } = string.Empty;

    [JsonPropertyName("model_profile_id")]
    public string? ModelProfileId { get; set; }

    [JsonPropertyName("trigger_type")]
    public TriggerType TriggerType { get; set; }

    [JsonPropertyName("trigger_expression")]
    public string TriggerExpression { get; set; } = string.Empty;

    [JsonPropertyName("timezone")]
    public string Timezone { get; set; } = "UTC";

    [JsonPropertyName("status")]
    public ScheduleStatus Status { get; set; }

    [JsonPropertyName("missed_run_policy")]
    public MissedRunPolicy MissedRunPolicy { get; set; }

    [JsonPropertyName("concurrency_policy")]
    public ConcurrencyPolicy ConcurrencyPolicy { get; set; }

    [JsonPropertyName("max_instances")]
    public int MaxInstances { get; set; } = 1;

    [JsonPropertyName("retry_grace_seconds")]
    public int RetryGraceSeconds { get; set; } = 300;

    [JsonPropertyName("next_run_at")]
    public DateTime? NextRunAt { get; set; }

    [JsonPropertyName("last_run_at")]
    public DateTime? LastRunAt { get; set; }

    [JsonPropertyName("template_hash")]
    public string TemplateHash { get; set; } = string.Empty;

    [JsonPropertyName("created_at")]
    public DateTime CreatedAt { get; set; }

    [JsonPropertyName("updated_at")]
    public DateTime UpdatedAt { get; set; }
}

public class ScheduleCreateRequest
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("prompt_template")]
    public string PromptTemplate { get; set; } = string.Empty;

    [JsonPropertyName("model_profile_id")]
    public string? ModelProfileId { get; set; }

    [JsonPropertyName("trigger_type")]
    public TriggerType TriggerType { get; set; }

    [JsonPropertyName("trigger_expression")]
    public string TriggerExpression { get; set; } = string.Empty;

    [JsonPropertyName("timezone")]
    public string Timezone { get; set; } = "UTC";

    [JsonPropertyName("missed_run_policy")]
    public MissedRunPolicy MissedRunPolicy { get; set; } = MissedRunPolicy.SKIP_NOTIFY;

    [JsonPropertyName("concurrency_policy")]
    public ConcurrencyPolicy ConcurrencyPolicy { get; set; } = ConcurrencyPolicy.SKIP_BUSY;

    [JsonPropertyName("max_instances")]
    public int MaxInstances { get; set; } = 1;

    [JsonPropertyName("retry_grace_seconds")]
    public int RetryGraceSeconds { get; set; } = 300;
}

public class ScheduleUpdateRequest
{
    [JsonPropertyName("name")]
    public string? Name { get; set; }

    [JsonPropertyName("prompt_template")]
    public string? PromptTemplate { get; set; }

    [JsonPropertyName("model_profile_id")]
    public string? ModelProfileId { get; set; }

    [JsonPropertyName("trigger_type")]
    public TriggerType? TriggerType { get; set; }

    [JsonPropertyName("trigger_expression")]
    public string? TriggerExpression { get; set; }

    [JsonPropertyName("timezone")]
    public string? Timezone { get; set; }

    [JsonPropertyName("missed_run_policy")]
    public MissedRunPolicy? MissedRunPolicy { get; set; }

    [JsonPropertyName("concurrency_policy")]
    public ConcurrencyPolicy? ConcurrencyPolicy { get; set; }

    [JsonPropertyName("retry_grace_seconds")]
    public int? RetryGraceSeconds { get; set; }
}

public class ScheduleRunDto
{
    [JsonPropertyName("run_id")]
    public string RunId { get; set; } = string.Empty;

    [JsonPropertyName("schedule_id")]
    public string ScheduleId { get; set; } = string.Empty;

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("run_key")]
    public string RunKey { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public RunStatus Status { get; set; }

    [JsonPropertyName("scheduled_for")]
    public DateTime ScheduledFor { get; set; }

    [JsonPropertyName("dispatched_at")]
    public DateTime DispatchedAt { get; set; }

    [JsonPropertyName("finished_at")]
    public DateTime? FinishedAt { get; set; }

    [JsonPropertyName("error_message")]
    public string? ErrorMessage { get; set; }
}
