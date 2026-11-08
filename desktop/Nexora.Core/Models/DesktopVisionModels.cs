using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Nexora.Desktop.Models;

public class WindowRectDto
{
    [JsonPropertyName("x")]
    public int X { get; set; }

    [JsonPropertyName("y")]
    public int Y { get; set; }

    [JsonPropertyName("width")]
    public int Width { get; set; }

    [JsonPropertyName("height")]
    public int Height { get; set; }
}

public class WindowSummaryDto
{
    [JsonPropertyName("hwnd")]
    public int Hwnd { get; set; }

    [JsonPropertyName("pid")]
    public int Pid { get; set; }

    [JsonPropertyName("process_name")]
    public string ProcessName { get; set; } = string.Empty;

    [JsonPropertyName("window_title")]
    public string WindowTitle { get; set; } = string.Empty;

    [JsonPropertyName("bounds")]
    public WindowRectDto Bounds { get; set; } = new();

    [JsonPropertyName("is_shielded")]
    public bool IsShielded { get; set; }
}

public class TargetWindowBindingDto
{
    [JsonPropertyName("hwnd")]
    public int Hwnd { get; set; }

    [JsonPropertyName("pid")]
    public int Pid { get; set; }

    [JsonPropertyName("process_name")]
    public string ProcessName { get; set; } = string.Empty;

    [JsonPropertyName("window_title")]
    public string WindowTitle { get; set; } = string.Empty;

    [JsonPropertyName("bounds")]
    public WindowRectDto Bounds { get; set; } = new();

    [JsonPropertyName("is_shielded")]
    public bool IsShielded { get; set; }
}

public class UIElementNodeDto
{
    [JsonPropertyName("element_id")]
    public string ElementId { get; set; } = string.Empty;

    [JsonPropertyName("automation_id")]
    public string AutomationId { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("control_type")]
    public string ControlType { get; set; } = "Unknown";

    [JsonPropertyName("bounding_rect")]
    public WindowRectDto BoundingRect { get; set; } = new();

    [JsonPropertyName("is_enabled")]
    public bool IsEnabled { get; set; } = true;

    [JsonPropertyName("is_password")]
    public bool IsPassword { get; set; }

    [JsonPropertyName("value")]
    public string? Value { get; set; }

    [JsonPropertyName("supported_patterns")]
    public List<string> SupportedPatterns { get; set; } = new();

    [JsonPropertyName("children")]
    public List<UIElementNodeDto> Children { get; set; } = new();
}

public class DesktopActionRequestDto
{
    [JsonPropertyName("binding")]
    public TargetWindowBindingDto Binding { get; set; } = new();

    [JsonPropertyName("action_type")]
    public string ActionType { get; set; } = "click";

    [JsonPropertyName("target_element_id")]
    public string? TargetElementId { get; set; }

    [JsonPropertyName("relative_coords")]
    public List<int>? RelativeCoords { get; set; }

    [JsonPropertyName("text_input")]
    public string? TextInput { get; set; }

    [JsonPropertyName("scroll_amount")]
    public int? ScrollAmount { get; set; }

    [JsonPropertyName("expected_postcondition")]
    public string? ExpectedPostcondition { get; set; }
}

public class DesktopActionResultDto
{
    [JsonPropertyName("action_id")]
    public string ActionId { get; set; } = string.Empty;

    [JsonPropertyName("action_type")]
    public string ActionType { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = "SUCCESS";

    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;

    [JsonPropertyName("verification_ok")]
    public bool VerificationOk { get; set; }

    [JsonPropertyName("pre_action_screenshot_id")]
    public string? PreActionScreenshotId { get; set; }

    [JsonPropertyName("post_action_screenshot_id")]
    public string? PostActionScreenshotId { get; set; }

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = string.Empty;
}

public class ScreenshotEvidenceDto
{
    [JsonPropertyName("image_id")]
    public string ImageId { get; set; } = string.Empty;

    [JsonPropertyName("task_id")]
    public string TaskId { get; set; } = string.Empty;

    [JsonPropertyName("hwnd")]
    public int Hwnd { get; set; }

    [JsonPropertyName("file_path")]
    public string FilePath { get; set; } = string.Empty;

    [JsonPropertyName("sha256_hash")]
    public string Sha256Hash { get; set; } = string.Empty;

    [JsonPropertyName("width")]
    public int Width { get; set; }

    [JsonPropertyName("height")]
    public int Height { get; set; }

    [JsonPropertyName("is_redacted")]
    public bool IsRedacted { get; set; }

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;

    [JsonPropertyName("expires_at")]
    public string ExpiresAt { get; set; } = string.Empty;
}

public class AutonomousSessionConfigDto
{
    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = string.Empty;

    [JsonPropertyName("goal")]
    public string Goal { get; set; } = string.Empty;

    [JsonPropertyName("allowed_hwnds")]
    public List<int> AllowedHwnds { get; set; } = new();

    [JsonPropertyName("max_actions")]
    public int MaxActions { get; set; } = 30;

    [JsonPropertyName("max_duration_seconds")]
    public double MaxDurationSeconds { get; set; } = 600.0;

    [JsonPropertyName("require_confirmation")]
    public bool RequireConfirmation { get; set; }
}

public class AutonomousSessionStateDto
{
    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = string.Empty;

    [JsonPropertyName("goal")]
    public string Goal { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = "READY";

    [JsonPropertyName("action_count")]
    public int ActionCount { get; set; }

    [JsonPropertyName("max_actions")]
    public int MaxActions { get; set; } = 30;

    [JsonPropertyName("elapsed_seconds")]
    public double ElapsedSeconds { get; set; }

    [JsonPropertyName("max_duration_seconds")]
    public double MaxDurationSeconds { get; set; } = 600.0;

    [JsonPropertyName("bound_hwnd")]
    public int? BoundHwnd { get; set; }

    [JsonPropertyName("last_action_message")]
    public string? LastActionMessage { get; set; }

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;

    [JsonPropertyName("updated_at")]
    public string UpdatedAt { get; set; } = string.Empty;
}

public class AutonomousStepResultDto
{
    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = string.Empty;

    [JsonPropertyName("step_number")]
    public int StepNumber { get; set; }

    [JsonPropertyName("action_result")]
    public DesktopActionResultDto? ActionResult { get; set; }

    [JsonPropertyName("session_state")]
    public AutonomousSessionStateDto SessionState { get; set; } = new();

    [JsonPropertyName("is_terminal")]
    public bool IsTerminal { get; set; }

    [JsonPropertyName("terminal_reason")]
    public string? TerminalReason { get; set; }
}
