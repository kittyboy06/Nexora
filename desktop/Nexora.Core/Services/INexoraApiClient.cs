using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Nexora.Desktop.Models;

namespace Nexora.Desktop.Services;

public interface INexoraApiClient
{
    Task<HealthResponse> GetHealthAsync(CancellationToken cancellationToken = default);
    Task<OllamaStatusResponse> GetOllamaStatusAsync(CancellationToken cancellationToken = default);
    Task<ModelProfileListResponse> GetModelProfilesAsync(bool refresh = false, CancellationToken cancellationToken = default);
    Task<AgentTask> CreateTaskAsync(string prompt, string? profileId = null, string? executionMode = "auto", CancellationToken cancellationToken = default);
    Task<AgentTask> GetTaskAsync(string taskId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<AgentTask>> ListTasksAsync(CancellationToken cancellationToken = default);
    Task<AgentTask> CancelTaskAsync(string taskId, CancellationToken cancellationToken = default);
    Task<AgentTask> DecideApprovalAsync(string taskId, string approvalId, bool approved, CancellationToken cancellationToken = default);

    // Phase 7: Skills and GitHub Discovery
    Task<IReadOnlyList<SkillSummaryDto>> ListSkillsAsync(bool enabledOnly = false, string? role = null, CancellationToken cancellationToken = default);
    Task<SkillBundleDto> GetSkillAsync(string skillId, string? version = null, CancellationToken cancellationToken = default);
    Task<SkillBundleDto> PatchSkillAsync(string skillId, bool? isEnabled = null, string? activeVersion = null, CancellationToken cancellationToken = default);
    Task<bool> DeleteSkillAsync(string skillId, string? version = null, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SkillDiscoveryCandidateDto>> SearchDiscoveryAsync(string query, int page = 1, int perPage = 10, CancellationToken cancellationToken = default);
    Task<SkillDiscoveryCandidateDto> PreviewDiscoveryAsync(string owner, string repo, string branch = "main", string? path = null, CancellationToken cancellationToken = default);
    Task<SkillBundleDto> InstallSkillAsync(InstallSkillRequestDto request, CancellationToken cancellationToken = default);
    Task<GitHubRateLimitStatusDto> GetGitHubRateLimitAsync(CancellationToken cancellationToken = default);

    // Phase 8: Universal MCP Platform
    Task<IReadOnlyList<McpServerRecordDto>> ListMcpServersAsync(CancellationToken cancellationToken = default);
    Task<McpServerRecordDto> GetMcpServerAsync(string serverId, CancellationToken cancellationToken = default);
    Task<McpServerRecordDto> RegisterMcpServerAsync(McpServerCreateRequestDto request, CancellationToken cancellationToken = default);
    Task<McpServerRecordDto> UpdateMcpServerAsync(string serverId, McpServerUpdateRequestDto request, CancellationToken cancellationToken = default);
    Task<bool> DeleteMcpServerAsync(string serverId, CancellationToken cancellationToken = default);
    Task<McpServerRecordDto> ApproveMcpServerAsync(string serverId, CancellationToken cancellationToken = default);
    Task<McpServerRecordDto> ConnectMcpServerAsync(string serverId, CancellationToken cancellationToken = default);
    Task<McpServerRecordDto> DisconnectMcpServerAsync(string serverId, CancellationToken cancellationToken = default);
    Task<McpPingResponseDto> PingMcpServerAsync(string serverId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<McpVaultItemSummaryDto>> ListMcpVaultSecretsAsync(CancellationToken cancellationToken = default);
    Task<McpVaultItemSummaryDto> WriteMcpVaultSecretAsync(McpVaultWriteRequestDto request, CancellationToken cancellationToken = default);
    Task<bool> DeleteMcpVaultSecretAsync(string key, CancellationToken cancellationToken = default);

    // Phase 9: Browser and Internet Research
    Task<IReadOnlyList<SearchResultDto>> SearchWebAsync(string query, int maxResults = 5, CancellationToken cancellationToken = default);
    Task<FetchResultDto> FetchWebpageAsync(string url, bool renderJs = false, bool takeScreenshot = false, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<ResearchEvidenceDto>> ListTaskEvidenceAsync(string taskId, CancellationToken cancellationToken = default);
    Task<ResearchEvidenceDto> GetEvidenceDetailAsync(string taskId, string evidenceId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<QuarantineItemDto>> ListQuarantinedDownloadsAsync(string taskId, CancellationToken cancellationToken = default);
    Task<bool> DeleteQuarantinedDownloadAsync(string taskId, string filename, CancellationToken cancellationToken = default);

    // Phase 10: Generated Tools and Sandbox Platform
    Task<ToolValidationReportDto> ValidateToolProposalAsync(GeneratedToolProposalDto proposal, CancellationToken cancellationToken = default);
    Task<SandboxRunResultDto> RunSandboxTrialAsync(TrialRunRequestDto request, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SandboxRunResultDto>> ListSandboxEvidenceAsync(int limit = 50, CancellationToken cancellationToken = default);
    Task<SandboxRunResultDto> GetSandboxEvidenceAsync(string runId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<GeneratedToolRecordDto>> ListGeneratedToolsAsync(CancellationToken cancellationToken = default);
    Task<GeneratedToolRecordDto> GetGeneratedToolAsync(string toolName, string? version = null, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<string>> ListGeneratedToolVersionsAsync(string toolName, CancellationToken cancellationToken = default);
    Task<GeneratedToolRecordDto> PromoteToolAsync(ToolPromotionRequestDto request, CancellationToken cancellationToken = default);
    Task<GeneratedToolRecordDto> UpdateGeneratedToolAsync(string toolName, ToolUpdateRequestDto request, CancellationToken cancellationToken = default);
    Task<bool> DeleteGeneratedToolAsync(string toolName, CancellationToken cancellationToken = default);

    // Phase 11: Memory and Persistence Platform
    Task<IReadOnlyList<MemoryRecordDto>> ListMemoriesAsync(string? category = null, string? status = null, string? query = null, int limit = 50, CancellationToken cancellationToken = default);
    Task<MemoryRecordDto> CreateMemoryAsync(MemoryProposalDto proposal, bool autoApprove = false, CancellationToken cancellationToken = default);
    Task<MemoryRecordDto> GetMemoryAsync(string memoryId, CancellationToken cancellationToken = default);
    Task<MemoryRecordDto> UpdateMemoryAsync(string memoryId, MemoryUpdateRequestDto request, CancellationToken cancellationToken = default);
    Task<MemoryRecordDto> ApproveMemoryAsync(string memoryId, CancellationToken cancellationToken = default);
    Task<bool> RevokeMemoryAsync(string memoryId, string reason = "Revoked by operator", CancellationToken cancellationToken = default);
    Task<bool> DeleteMemoryAsync(string memoryId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<MemoryAuditEntryDto>> ListMemoryAuditAsync(string? memoryId = null, int limit = 50, CancellationToken cancellationToken = default);
    Task<MemoryBackupInfoDto> CreateMemoryBackupAsync(CancellationToken cancellationToken = default);
    Task<IReadOnlyList<MemoryBackupInfoDto>> ListMemoryBackupsAsync(CancellationToken cancellationToken = default);
    Task<bool> RestoreMemoryBackupAsync(string backupPath, CancellationToken cancellationToken = default);
    Task<string> ExportMemoriesAsync(string format = "json", CancellationToken cancellationToken = default);
}
