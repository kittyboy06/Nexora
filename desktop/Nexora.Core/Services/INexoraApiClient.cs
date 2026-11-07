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
}
