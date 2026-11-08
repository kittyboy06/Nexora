using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class ChatViewModelTests
{
    private class MockApiClient : INexoraApiClient
    {
        public List<Conversation> ConversationsList { get; set; } = new();
        public Conversation? FullConversation { get; set; }
        public ConversationMessageResponse? ChatResponseToReturn { get; set; }
        public bool CreateCalled { get; set; }
        public bool DeleteCalled { get; set; }
        public string? LastDeletedId { get; set; }

        public Task<HealthResponse> GetHealthAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<OllamaStatusResponse> GetOllamaStatusAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<string> GetActiveModelAsync(CancellationToken cancellationToken = default) => Task.FromResult("llama3:latest");
        public Task<bool> SetActiveModelAsync(string modelName, CancellationToken cancellationToken = default) => Task.FromResult(true);
        public Task<ModelProfileListResponse> GetModelProfilesAsync(bool refresh = false, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AgentTask> CreateTaskAsync(string prompt, string? profileId = null, string? executionMode = "auto", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AgentTask> GetTaskAsync(string taskId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<AgentTask>> ListTasksAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AgentTask> CancelTaskAsync(string taskId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AgentTask> DecideApprovalAsync(string taskId, string approvalId, bool approved, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<SkillSummaryDto>> ListSkillsAsync(bool enabledOnly = false, string? role = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillBundleDto> GetSkillAsync(string skillId, string? version = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillBundleDto> PatchSkillAsync(string skillId, bool? isEnabled = null, string? activeVersion = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteSkillAsync(string skillId, string? version = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<SkillDiscoveryCandidateDto>> SearchDiscoveryAsync(string query, int page = 1, int perPage = 10, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillDiscoveryCandidateDto> PreviewDiscoveryAsync(string owner, string repo, string branch = "main", string? path = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillBundleDto> InstallSkillAsync(InstallSkillRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillBundleDto> ImportSkillFolderAsync(SkillImportFolderRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillBundleDto> ImportSkillPasteAsync(SkillImportPasteRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SkillReadmePreviewResponseDto> PreviewSkillReadmeAsync(string owner, string repo, string branch = "main", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<GitHubRateLimitStatusDto> GetGitHubRateLimitAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<McpServerRecordDto>> ListMcpServersAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> GetMcpServerAsync(string serverId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> RegisterMcpServerAsync(McpServerCreateRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> UpdateMcpServerAsync(string serverId, McpServerUpdateRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteMcpServerAsync(string serverId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> ApproveMcpServerAsync(string serverId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpInspectionReportDto> InspectMcpManifestAsync(McpServerCreateRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpTestConnectionResultDto> TestMcpConnectionAsync(McpServerCreateRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> ApproveMcpManifestAsync(McpOnboardApproveRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> ConnectMcpServerAsync(string serverId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpServerRecordDto> DisconnectMcpServerAsync(string serverId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpPingResponseDto> PingMcpServerAsync(string serverId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<McpVaultItemSummaryDto>> ListMcpVaultSecretsAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<McpVaultItemSummaryDto> WriteMcpVaultSecretAsync(McpVaultWriteRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteMcpVaultSecretAsync(string key, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<SearchResultDto>> SearchWebAsync(string query, int maxResults = 5, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<FetchResultDto> FetchWebpageAsync(string url, bool renderJs = false, bool takeScreenshot = false, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<ResearchEvidenceDto>> ListTaskEvidenceAsync(string taskId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ResearchEvidenceDto> GetEvidenceDetailAsync(string taskId, string evidenceId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<QuarantineItemDto>> ListQuarantinedDownloadsAsync(string taskId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteQuarantinedDownloadAsync(string taskId, string filename, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ToolValidationReportDto> ValidateToolProposalAsync(GeneratedToolProposalDto proposal, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SandboxRunResultDto> RunSandboxTrialAsync(TrialRunRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<SandboxRunResultDto>> ListSandboxEvidenceAsync(int limit = 50, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<SandboxRunResultDto> GetSandboxEvidenceAsync(string runId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<GeneratedToolRecordDto>> ListGeneratedToolsAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<GeneratedToolRecordDto> GetGeneratedToolAsync(string toolName, string? version = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<string>> ListGeneratedToolVersionsAsync(string toolName, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<GeneratedToolRecordDto> PromoteToolAsync(ToolPromotionRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<GeneratedToolRecordDto> UpdateGeneratedToolAsync(string toolName, ToolUpdateRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteGeneratedToolAsync(string toolName, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<MemoryRecordDto>> ListMemoriesAsync(string? category = null, string? status = null, string? query = null, int limit = 50, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<MemoryRecordDto> CreateMemoryAsync(MemoryProposalDto proposal, bool autoApprove = false, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<MemoryRecordDto> GetMemoryAsync(string memoryId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<MemoryRecordDto> UpdateMemoryAsync(string memoryId, MemoryUpdateRequestDto request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<MemoryRecordDto> ApproveMemoryAsync(string memoryId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> RevokeMemoryAsync(string memoryId, string reason = "Revoked by operator", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteMemoryAsync(string memoryId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<MemoryAuditEntryDto>> ListMemoryAuditAsync(string? memoryId = null, int limit = 50, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<MemoryBackupInfoDto> CreateMemoryBackupAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<MemoryBackupInfoDto>> ListMemoryBackupsAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> RestoreMemoryBackupAsync(string backupPath, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<string> ExportMemoriesAsync(string format = "json", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<WindowSummaryDto>> ListDesktopWindowsAsync(string? query = null, bool includeShielded = false, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<TargetWindowBindingDto> BindDesktopWindowAsync(int hwnd, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<TargetWindowBindingDto?> GetActiveDesktopBindingAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> ReleaseDesktopBindingAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<UIElementNodeDto> InspectDesktopTreeAsync(int? hwnd = null, int maxDepth = 4, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScreenshotEvidenceDto> CaptureDesktopWindowAsync(int? hwnd = null, string taskId = "default_task", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<DesktopActionResultDto> ExecuteDesktopActionAsync(DesktopActionRequestDto request, string taskId = "default_task", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> TriggerEmergencyStopAsync(string reason = "Operator emergency stop", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> ResetEmergencyStopAsync(CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<ScreenshotEvidenceDto>> ListDesktopEvidenceAsync(string? taskId = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AutonomousSessionStateDto> StartAutonomousSessionAsync(AutonomousSessionConfigDto config, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AutonomousStepResultDto> ExecuteAutonomousStepAsync(string sessionId, DesktopActionRequestDto? action = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AutonomousSessionStateDto> PauseAutonomousSessionAsync(string sessionId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AutonomousSessionStateDto> ResumeAutonomousSessionAsync(string sessionId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AutonomousSessionStateDto> StopAutonomousSessionAsync(string sessionId, string reason = "Stopped by operator", CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<AutonomousSessionStateDto> GetAutonomousSessionAsync(string sessionId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<ScheduleDto>> ListSchedulesAsync(string? status = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScheduleDto> CreateScheduleAsync(ScheduleCreateRequest request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScheduleDto> GetScheduleAsync(string scheduleId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScheduleDto> UpdateScheduleAsync(string scheduleId, ScheduleUpdateRequest request, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScheduleDto> PauseScheduleAsync(string scheduleId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScheduleDto> ResumeScheduleAsync(string scheduleId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<bool> DeleteScheduleAsync(string scheduleId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<ScheduleRunDto> TriggerScheduleAsync(string scheduleId, CancellationToken cancellationToken = default) => throw new NotImplementedException();
        public Task<IReadOnlyList<ScheduleRunDto>> ListScheduleRunsAsync(string? scheduleId = null, string? status = null, int limit = 50, CancellationToken cancellationToken = default) => throw new NotImplementedException();

        // Phase 15 Conversation Methods
        public Task<IReadOnlyList<Conversation>> ListConversationsAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult<IReadOnlyList<Conversation>>(ConversationsList);
        }

        public Task<Conversation> GetConversationAsync(string conversationId, CancellationToken cancellationToken = default)
        {
            if (FullConversation != null && FullConversation.ConversationId == conversationId)
            {
                return Task.FromResult(FullConversation);
            }
            return Task.FromResult(new Conversation(
                conversationId,
                "Test Conversation",
                DateTimeOffset.UtcNow,
                DateTimeOffset.UtcNow,
                false,
                new List<ConversationMessage>(),
                new List<ConversationWorkItem>()
            ));
        }

        public Task<Conversation> CreateConversationAsync(string? title = null, CancellationToken cancellationToken = default)
        {
            CreateCalled = true;
            var created = new Conversation(
                $"conv_{Guid.NewGuid():N}",
                title ?? "New Conversation",
                DateTimeOffset.UtcNow,
                DateTimeOffset.UtcNow,
                false,
                new List<ConversationMessage>(),
                new List<ConversationWorkItem>()
            );
            ConversationsList.Insert(0, created);
            return Task.FromResult(created);
        }

        public Task<bool> DeleteConversationAsync(string conversationId, CancellationToken cancellationToken = default)
        {
            DeleteCalled = true;
            LastDeletedId = conversationId;
            ConversationsList.RemoveAll(c => c.ConversationId == conversationId);
            return Task.FromResult(true);
        }

        public Task<ConversationMessageResponse> SendChatMessageAsync(string conversationId, string content, ChatMode mode = ChatMode.Auto, string? modelOverride = null, CancellationToken cancellationToken = default)
        {
            if (ChatResponseToReturn != null)
            {
                return Task.FromResult(ChatResponseToReturn);
            }

            var msg = new ConversationMessage(
                $"msg_{Guid.NewGuid():N}",
                conversationId,
                "assistant",
                $"Echo response to: {content}",
                mode,
                modelOverride ?? "llama3",
                null,
                new List<string>(),
                DateTimeOffset.UtcNow
            );

            return Task.FromResult(new ConversationMessageResponse(
                msg,
                null
            ));
        }
    }

    [Fact]
    public async Task LoadConversationsAsync_WhenEmpty_CreatesNewConversation()
    {
        var mock = new MockApiClient();
        var vm = new ChatViewModel(mock);

        await vm.LoadConversationsAsync();

        Assert.True(mock.CreateCalled);
        Assert.Single(vm.Conversations);
        Assert.NotNull(vm.CurrentConversation);
    }

    [Fact]
    public async Task SendMessageAsync_AddsUserAndAssistantMessages()
    {
        var mock = new MockApiClient();
        var vm = new ChatViewModel(mock);
        await vm.LoadConversationsAsync();

        vm.ComposerText = "Hello Nexora";
        await vm.SendMessageAsync();

        Assert.Equal(2, vm.Messages.Count);
        Assert.Equal("user", vm.Messages[0].Role);
        Assert.Equal("Hello Nexora", vm.Messages[0].Content);
        Assert.Equal("assistant", vm.Messages[1].Role);
        Assert.Contains("Echo response to: Hello Nexora", vm.Messages[1].Content);
    }

    [Fact]
    public async Task SendMessageAsync_WhenWorkItemReturned_PopulatesWorkItems()
    {
        var mock = new MockApiClient();
        var workItem = new ConversationWorkItem(
            WorkItemId: "wi_123",
            ConversationId: "conv_1",
            SourceMessageId: "msg_user",
            Intent: WorkItemIntent.Task,
            TargetModule: "agent.task",
            TargetId: "task_456",
            Status: WorkItemStatus.Running,
            Summary: "Inspect Python repo",
            Routing: null,
            AuthorizationState: AuthorizationState.None,
            EvidenceRefs: new List<string>(),
            CreatedAt: DateTimeOffset.UtcNow,
            UpdatedAt: DateTimeOffset.UtcNow
        );

        mock.ChatResponseToReturn = new ConversationMessageResponse(
            Message: new ConversationMessage(
                "msg_reply",
                "conv_1",
                "assistant",
                "Started task task_456",
                ChatMode.Task,
                "llama3",
                null,
                new List<string> { "wi_123" },
                DateTimeOffset.UtcNow
            ),
            WorkItem: workItem
        );

        var vm = new ChatViewModel(mock);
        await vm.LoadConversationsAsync();

        vm.ComposerText = "Please inspect repo";
        await vm.SendMessageAsync();

        Assert.Single(vm.WorkItems);
        Assert.Equal("wi_123", vm.WorkItems[0].WorkItemId);
        Assert.Equal("task_456", vm.WorkItems[0].TargetId);
        Assert.Equal(WorkItemIntent.Task, vm.WorkItems[0].Intent);
    }

    [Fact]
    public void NavigateToWorkItem_RaisesEvent()
    {
        var mock = new MockApiClient();
        var vm = new ChatViewModel(mock);

        ConversationWorkItem? received = null;
        vm.WorkItemNavigationRequested += item => received = item;

        var target = new ConversationWorkItem(
            WorkItemId: "wi_789",
            ConversationId: "conv_1",
            SourceMessageId: "msg_1",
            Intent: WorkItemIntent.SkillImport,
            TargetModule: "skills",
            TargetId: "skill_git",
            Status: WorkItemStatus.Completed,
            Summary: "Import Git skill",
            Routing: null,
            AuthorizationState: AuthorizationState.None,
            EvidenceRefs: new List<string>(),
            CreatedAt: DateTimeOffset.UtcNow,
            UpdatedAt: DateTimeOffset.UtcNow
        );

        vm.NavigateToWorkItem(target);

        Assert.NotNull(received);
        Assert.Equal("wi_789", received.WorkItemId);
        Assert.Equal(WorkItemIntent.SkillImport, received.Intent);
    }
}
