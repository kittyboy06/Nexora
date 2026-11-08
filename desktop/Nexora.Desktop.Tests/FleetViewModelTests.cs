using System.Collections.Generic;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class FleetViewModelTests
{
    private class DummyApiClient : INexoraApiClient
    {
        public System.Threading.Tasks.Task<HealthResponse> GetHealthAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<OllamaStatusResponse> GetOllamaStatusAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<string> GetActiveModelAsync(System.Threading.CancellationToken cancellationToken = default) => System.Threading.Tasks.Task.FromResult("llama3:latest");
        public System.Threading.Tasks.Task<bool> SetActiveModelAsync(string modelName, System.Threading.CancellationToken cancellationToken = default) => System.Threading.Tasks.Task.FromResult(true);
        public System.Threading.Tasks.Task<ModelProfileListResponse> GetModelProfilesAsync(bool refresh = false, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> CreateTaskAsync(string prompt, string? profileId = null, string? executionMode = "auto", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> GetTaskAsync(string taskId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<IReadOnlyList<AgentTask>> ListTasksAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> CancelTaskAsync(string taskId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> DecideApprovalAsync(string taskId, string approvalId, bool approved, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<IReadOnlyList<SkillSummaryDto>> ListSkillsAsync(bool enabledOnly = false, string? role = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillBundleDto> GetSkillAsync(string skillId, string? version = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillBundleDto> PatchSkillAsync(string skillId, bool? isEnabled = null, string? activeVersion = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteSkillAsync(string skillId, string? version = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<IReadOnlyList<SkillDiscoveryCandidateDto>> SearchDiscoveryAsync(string query, int page = 1, int perPage = 10, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillDiscoveryCandidateDto> PreviewDiscoveryAsync(string owner, string repo, string branch = "main", string? path = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillBundleDto> InstallSkillAsync(InstallSkillRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillBundleDto> ImportSkillFolderAsync(SkillImportFolderRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillBundleDto> ImportSkillPasteAsync(SkillImportPasteRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SkillReadmePreviewResponseDto> PreviewSkillReadmeAsync(string owner, string repo, string branch = "main", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<GitHubRateLimitStatusDto> GetGitHubRateLimitAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<McpServerRecordDto>> ListMcpServersAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> GetMcpServerAsync(string serverId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> RegisterMcpServerAsync(McpServerCreateRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> UpdateMcpServerAsync(string serverId, McpServerUpdateRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteMcpServerAsync(string serverId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> ApproveMcpServerAsync(string serverId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpInspectionReportDto> InspectMcpManifestAsync(McpServerCreateRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpTestConnectionResultDto> TestMcpConnectionAsync(McpServerCreateRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> ApproveMcpManifestAsync(McpOnboardApproveRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> ConnectMcpServerAsync(string serverId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpServerRecordDto> DisconnectMcpServerAsync(string serverId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpPingResponseDto> PingMcpServerAsync(string serverId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<McpVaultItemSummaryDto>> ListMcpVaultSecretsAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<McpVaultItemSummaryDto> WriteMcpVaultSecretAsync(McpVaultWriteRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteMcpVaultSecretAsync(string key, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<SearchResultDto>> SearchWebAsync(string query, int maxResults = 5, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<FetchResultDto> FetchWebpageAsync(string url, bool renderJs = false, bool takeScreenshot = false, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<ResearchEvidenceDto>> ListTaskEvidenceAsync(string taskId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ResearchEvidenceDto> GetEvidenceDetailAsync(string taskId, string evidenceId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<QuarantineItemDto>> ListQuarantinedDownloadsAsync(string taskId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteQuarantinedDownloadAsync(string taskId, string filename, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ToolValidationReportDto> ValidateToolProposalAsync(GeneratedToolProposalDto proposal, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SandboxRunResultDto> RunSandboxTrialAsync(TrialRunRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<SandboxRunResultDto>> ListSandboxEvidenceAsync(int limit = 50, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<SandboxRunResultDto> GetSandboxEvidenceAsync(string runId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<GeneratedToolRecordDto>> ListGeneratedToolsAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<GeneratedToolRecordDto> GetGeneratedToolAsync(string toolName, string? version = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<string>> ListGeneratedToolVersionsAsync(string toolName, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<GeneratedToolRecordDto> PromoteToolAsync(ToolPromotionRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<GeneratedToolRecordDto> UpdateGeneratedToolAsync(string toolName, ToolUpdateRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteGeneratedToolAsync(string toolName, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<MemoryRecordDto>> ListMemoriesAsync(string? category = null, string? status = null, string? query = null, int limit = 50, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<MemoryRecordDto> CreateMemoryAsync(MemoryProposalDto proposal, bool autoApprove = false, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<MemoryRecordDto> GetMemoryAsync(string memoryId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<MemoryRecordDto> UpdateMemoryAsync(string memoryId, MemoryUpdateRequestDto request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<MemoryRecordDto> ApproveMemoryAsync(string memoryId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> RevokeMemoryAsync(string memoryId, string reason = "Revoked by operator", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteMemoryAsync(string memoryId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<MemoryAuditEntryDto>> ListMemoryAuditAsync(string? memoryId = null, int limit = 50, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<MemoryBackupInfoDto> CreateMemoryBackupAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<MemoryBackupInfoDto>> ListMemoryBackupsAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> RestoreMemoryBackupAsync(string backupPath, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<string> ExportMemoriesAsync(string format = "json", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<WindowSummaryDto>> ListDesktopWindowsAsync(string? query = null, bool includeShielded = false, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<TargetWindowBindingDto> BindDesktopWindowAsync(int hwnd, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<TargetWindowBindingDto?> GetActiveDesktopBindingAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> ReleaseDesktopBindingAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<UIElementNodeDto> InspectDesktopTreeAsync(int? hwnd = null, int maxDepth = 4, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScreenshotEvidenceDto> CaptureDesktopWindowAsync(int? hwnd = null, string taskId = "default_task", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<DesktopActionResultDto> ExecuteDesktopActionAsync(DesktopActionRequestDto request, string taskId = "default_task", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> TriggerEmergencyStopAsync(string reason = "Operator emergency stop", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> ResetEmergencyStopAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<ScreenshotEvidenceDto>> ListDesktopEvidenceAsync(string? taskId = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AutonomousSessionStateDto> StartAutonomousSessionAsync(AutonomousSessionConfigDto config, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AutonomousStepResultDto> ExecuteAutonomousStepAsync(string sessionId, DesktopActionRequestDto? action = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AutonomousSessionStateDto> PauseAutonomousSessionAsync(string sessionId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AutonomousSessionStateDto> ResumeAutonomousSessionAsync(string sessionId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AutonomousSessionStateDto> StopAutonomousSessionAsync(string sessionId, string reason = "Stopped by operator", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AutonomousSessionStateDto> GetAutonomousSessionAsync(string sessionId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<ScheduleDto>> ListSchedulesAsync(string? status = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScheduleDto> CreateScheduleAsync(ScheduleCreateRequest request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScheduleDto> GetScheduleAsync(string scheduleId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScheduleDto> UpdateScheduleAsync(string scheduleId, ScheduleUpdateRequest request, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScheduleDto> PauseScheduleAsync(string scheduleId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScheduleDto> ResumeScheduleAsync(string scheduleId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteScheduleAsync(string scheduleId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ScheduleRunDto> TriggerScheduleAsync(string scheduleId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<ScheduleRunDto>> ListScheduleRunsAsync(string? scheduleId = null, string? status = null, int limit = 50, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<System.Collections.Generic.IReadOnlyList<Conversation>> ListConversationsAsync(System.Threading.CancellationToken cancellationToken = default) => System.Threading.Tasks.Task.FromResult<System.Collections.Generic.IReadOnlyList<Conversation>>(new System.Collections.Generic.List<Conversation>());
        public System.Threading.Tasks.Task<Conversation> CreateConversationAsync(string? title = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<Conversation> GetConversationAsync(string conversationId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<bool> DeleteConversationAsync(string conversationId, System.Threading.CancellationToken cancellationToken = default) => System.Threading.Tasks.Task.FromResult(true);
        public System.Threading.Tasks.Task<ConversationMessageResponse> SendChatMessageAsync(string conversationId, string content, ChatMode mode = ChatMode.Auto, string? modelOverride = null, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
    }

    private class DummyPoller : ITaskPoller
    {
        public bool IsPolling => false;
        public string? CurrentTaskId => null;
        public event System.Action<AgentTask>? TaskUpdated;
        public event System.Action<AgentTask>? TerminalStateReached;
        public event System.Action<AgentTask>? ApprovalRequired;
        public void StartPolling(string taskId, System.TimeSpan? interval = null) { }
        public void StopPolling() { }
        public void Dispose() { }
    }

    [Fact]
    public void FleetNodeViewModel_StatusBadgeMappings()
    {
        var node = new FleetNodeViewModel
        {
            NodeId = "n1",
            Role = "researcher",
            Objective = "Read files",
            State = FleetNodeState.RUNNING,
        };

        Assert.Equal("● Running", node.StatusBadgeText);
        Assert.Equal("#0078D4", node.StatusColor);
        Assert.True(node.IsRunning);
        Assert.False(node.IsCompleted);

        node.State = FleetNodeState.COMPLETED;
        Assert.Equal("✓ Done", node.StatusBadgeText);
        Assert.Equal("#107C41", node.StatusColor);
        Assert.True(node.IsCompleted);
        Assert.False(node.IsRunning);

        node.State = FleetNodeState.BLOCKED;
        Assert.Equal("⊘ Blocked", node.StatusBadgeText);
        Assert.Equal("#A80000", node.StatusColor);
        Assert.True(node.IsBlocked);
    }

    [Fact]
    public void TaskDetailViewModel_PopulatesFleetNodes_FromFleetPlan()
    {
        var poller = new DummyPoller();
        var client = new DummyApiClient();
        var vm = new TaskDetailViewModel(client, poller);

        Assert.False(vm.HasFleetNodes);

        var node1 = new FleetNodeModel(
            NodeId: "n1",
            Role: "planner",
            Objective: "Decompose task",
            State: FleetNodeState.COMPLETED
        );
        var node2 = new FleetNodeModel(
            NodeId: "n2",
            Role: "coder",
            Objective: "Write implementation",
            Dependencies: new List<string> { "n1" },
            State: FleetNodeState.RUNNING
        );

        var fleetPlan = new FleetPlanModel(
            FleetId: "f1",
            ParentTaskId: "t1",
            Goal: "Complete feature",
            Nodes: new Dictionary<string, FleetNodeModel>
            {
                ["n1"] = node1,
                ["n2"] = node2,
            }
        );

        var artifact = new ArtifactModel(
            ArtifactId: "art_1",
            NodeId: "n1",
            ProducerRole: "planner",
            SchemaVersion: "1.0",
            Content: "plan completed",
            ContentHash: "hash123"
        );

        var task = new AgentTask(
            TaskId: "t1",
            Prompt: "Do feature",
            FleetPlan: fleetPlan,
            Artifacts: new List<ArtifactModel> { artifact }
        );

        vm.LoadTask(task);

        Assert.True(vm.HasFleetNodes);
        Assert.Equal(2, vm.FleetNodes.Count);
        Assert.Equal("n1", vm.FleetNodes[0].NodeId);
        Assert.Equal("planner", vm.FleetNodes[0].Role);
        Assert.Equal(FleetNodeState.COMPLETED, vm.FleetNodes[0].State);
        Assert.Equal("n2", vm.FleetNodes[1].NodeId);
        Assert.Equal("coder", vm.FleetNodes[1].Role);
        Assert.Equal(FleetNodeState.RUNNING, vm.FleetNodes[1].State);

        Assert.Single(vm.Artifacts);
        Assert.Equal("art_1", vm.Artifacts[0].ArtifactId);
    }
}
