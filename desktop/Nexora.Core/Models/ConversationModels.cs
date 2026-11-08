using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum ChatMode
{
    [JsonPropertyName("auto")]
    Auto,
    [JsonPropertyName("answer_only")]
    AnswerOnly,
    [JsonPropertyName("task")]
    Task,
    [JsonPropertyName("research")]
    Research,
    [JsonPropertyName("desktop_vision")]
    DesktopVision,
    [JsonPropertyName("schedule")]
    Schedule
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum WorkItemIntent
{
    [JsonPropertyName("answer")]
    Answer,
    [JsonPropertyName("task")]
    Task,
    [JsonPropertyName("research")]
    Research,
    [JsonPropertyName("skill_import")]
    SkillImport,
    [JsonPropertyName("mcp_onboard")]
    McpOnboard,
    [JsonPropertyName("desktop_vision")]
    DesktopVision,
    [JsonPropertyName("schedule")]
    Schedule
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum WorkItemStatus
{
    [JsonPropertyName("draft")]
    Draft,
    [JsonPropertyName("awaiting_confirmation")]
    AwaitingConfirmation,
    [JsonPropertyName("running")]
    Running,
    [JsonPropertyName("waiting_approval")]
    WaitingApproval,
    [JsonPropertyName("completed")]
    Completed,
    [JsonPropertyName("failed")]
    Failed,
    [JsonPropertyName("cancelled")]
    Cancelled
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum AuthorizationState
{
    [JsonPropertyName("none")]
    None,
    [JsonPropertyName("confirmation_needed")]
    ConfirmationNeeded,
    [JsonPropertyName("approval_pending")]
    ApprovalPending,
    [JsonPropertyName("approved")]
    Approved,
    [JsonPropertyName("rejected")]
    Rejected,
    [JsonPropertyName("expired")]
    Expired
}

public record ConversationWorkItem(
    [property: JsonPropertyName("work_item_id")] string WorkItemId,
    [property: JsonPropertyName("conversation_id")] string ConversationId,
    [property: JsonPropertyName("source_message_id")] string SourceMessageId,
    [property: JsonPropertyName("intent")] WorkItemIntent Intent,
    [property: JsonPropertyName("target_module")] string TargetModule,
    [property: JsonPropertyName("target_id")] string? TargetId,
    [property: JsonPropertyName("status")] WorkItemStatus Status,
    [property: JsonPropertyName("summary")] string Summary,
    [property: JsonPropertyName("routing")] Dictionary<string, object>? Routing,
    [property: JsonPropertyName("authorization_state")] AuthorizationState AuthorizationState,
    [property: JsonPropertyName("evidence_refs")] List<string> EvidenceRefs,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt,
    [property: JsonPropertyName("updated_at")] DateTimeOffset UpdatedAt
);

public record ConversationMessage(
    [property: JsonPropertyName("message_id")] string MessageId,
    [property: JsonPropertyName("conversation_id")] string ConversationId,
    [property: JsonPropertyName("role")] string Role,
    [property: JsonPropertyName("content")] string Content,
    [property: JsonPropertyName("mode")] ChatMode Mode,
    [property: JsonPropertyName("model")] string? Model,
    [property: JsonPropertyName("routing")] Dictionary<string, object>? Routing,
    [property: JsonPropertyName("work_item_ids")] List<string> WorkItemIds,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt
);

public record ConversationEvent(
    [property: JsonPropertyName("event_id")] string EventId,
    [property: JsonPropertyName("conversation_id")] string ConversationId,
    [property: JsonPropertyName("work_item_id")] string? WorkItemId,
    [property: JsonPropertyName("event_type")] string EventType,
    [property: JsonPropertyName("payload")] Dictionary<string, object> Payload,
    [property: JsonPropertyName("timestamp")] DateTimeOffset Timestamp
);

public record Conversation(
    [property: JsonPropertyName("conversation_id")] string ConversationId,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt,
    [property: JsonPropertyName("updated_at")] DateTimeOffset UpdatedAt,
    [property: JsonPropertyName("archived")] bool Archived,
    [property: JsonPropertyName("messages")] List<ConversationMessage> Messages,
    [property: JsonPropertyName("work_items")] List<ConversationWorkItem> WorkItems
);

public record ConversationCreateRequest(
    [property: JsonPropertyName("title")] string? Title = null
);

public record ConversationMessageRequest(
    [property: JsonPropertyName("content")] string Content,
    [property: JsonPropertyName("mode")] ChatMode Mode = ChatMode.Auto,
    [property: JsonPropertyName("model_override")] string? ModelOverride = null
);

public record ConversationResponse(
    [property: JsonPropertyName("conversation")] Conversation Conversation
);

public record ConversationListResponse(
    [property: JsonPropertyName("conversations")] List<Conversation> Conversations,
    [property: JsonPropertyName("count")] int Count
);

public record ConversationMessageResponse(
    [property: JsonPropertyName("message")] ConversationMessage Message,
    [property: JsonPropertyName("work_item")] ConversationWorkItem? WorkItem = null
);
