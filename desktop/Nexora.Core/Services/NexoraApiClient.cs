using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Nexora.Desktop.Models;

namespace Nexora.Desktop.Services;

public class NexoraApiClient : INexoraApiClient
{
    private readonly HttpClient _httpClient;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    public NexoraApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        if (_httpClient.BaseAddress == null)
        {
            _httpClient.BaseAddress = new Uri("http://127.0.0.1:8000");
        }
    }

    private async Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        try
        {
            var errorResponse = await response.Content.ReadFromJsonAsync<ErrorResponse>(JsonOptions, cancellationToken);
            if (errorResponse?.Error != null)
            {
                throw NexoraApiException.FromErrorResponse(errorResponse, (int)response.StatusCode);
            }
        }
        catch (JsonException)
        {
            // Not a structured ErrorResponse JSON
        }

        var rawBody = await response.Content.ReadAsStringAsync(cancellationToken);
        throw new NexoraApiException(
            message: string.IsNullOrWhiteSpace(rawBody) ? $"HTTP {(int)response.StatusCode} {response.ReasonPhrase}" : rawBody,
            code: "HTTP_ERROR",
            statusCode: (int)response.StatusCode
        );
    }

    public async Task<HealthResponse> GetHealthAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/health", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<HealthResponse>(JsonOptions, cancellationToken))!;
    }

    public async Task<OllamaStatusResponse> GetOllamaStatusAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/ollama/status", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<OllamaStatusResponse>(JsonOptions, cancellationToken))!;
    }

    public async Task<ModelProfileListResponse> GetModelProfilesAsync(bool refresh = false, CancellationToken cancellationToken = default)
    {
        var url = refresh ? "/api/ollama/profiles?refresh=true" : "/api/ollama/profiles";
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<ModelProfileListResponse>(JsonOptions, cancellationToken))!;
    }

    public async Task<AgentTask> CreateTaskAsync(string prompt, string? profileId = null, string? executionMode = "auto", CancellationToken cancellationToken = default)
    {
        var request = new TaskCreateRequest(Prompt: prompt, ModelProfileId: profileId, ExecutionMode: executionMode);
        var response = await _httpClient.PostAsJsonAsync("/api/agent/tasks", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<TaskResponse>(JsonOptions, cancellationToken);
        return body!.Task;
    }

    public async Task<AgentTask> GetTaskAsync(string taskId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/agent/tasks/{taskId}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<TaskResponse>(JsonOptions, cancellationToken);
        return body!.Task;
    }

    public async Task<IReadOnlyList<AgentTask>> ListTasksAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/agent/tasks", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<TaskListResponse>(JsonOptions, cancellationToken);
        return body?.Tasks ?? new List<AgentTask>();
    }

    public async Task<AgentTask> CancelTaskAsync(string taskId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/agent/tasks/{taskId}/cancel", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<TaskResponse>(JsonOptions, cancellationToken);
        return body!.Task;
    }

    public async Task<AgentTask> DecideApprovalAsync(string taskId, string approvalId, bool approved, CancellationToken cancellationToken = default)
    {
        var request = new ApprovalDecisionRequest(ApprovalId: approvalId, Approved: approved);
        var response = await _httpClient.PostAsJsonAsync($"/api/agent/tasks/{taskId}/approve", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<TaskResponse>(JsonOptions, cancellationToken);
        return body!.Task;
    }

    // Phase 7: Skills and GitHub Discovery
    public async Task<IReadOnlyList<SkillSummaryDto>> ListSkillsAsync(bool enabledOnly = false, string? role = null, CancellationToken cancellationToken = default)
    {
        var url = $"/api/skills?enabled_only={enabledOnly.ToString().ToLowerInvariant()}";
        if (!string.IsNullOrEmpty(role))
        {
            url += $"&role={Uri.EscapeDataString(role)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<List<SkillSummaryDto>>(JsonOptions, cancellationToken);
        return body ?? new List<SkillSummaryDto>();
    }

    public async Task<SkillBundleDto> GetSkillAsync(string skillId, string? version = null, CancellationToken cancellationToken = default)
    {
        var url = $"/api/skills/{Uri.EscapeDataString(skillId)}";
        if (!string.IsNullOrEmpty(version))
        {
            url += $"?version={Uri.EscapeDataString(version)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<SkillBundleDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<SkillBundleDto> PatchSkillAsync(string skillId, bool? isEnabled = null, string? activeVersion = null, CancellationToken cancellationToken = default)
    {
        var payload = new Dictionary<string, object?>();
        if (isEnabled.HasValue) payload["is_enabled"] = isEnabled.Value;
        if (!string.IsNullOrEmpty(activeVersion)) payload["active_version"] = activeVersion;

        var response = await _httpClient.PatchAsJsonAsync($"/api/skills/{Uri.EscapeDataString(skillId)}", payload, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<SkillBundleDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<bool> DeleteSkillAsync(string skillId, string? version = null, CancellationToken cancellationToken = default)
    {
        var url = $"/api/skills/{Uri.EscapeDataString(skillId)}";
        if (!string.IsNullOrEmpty(version))
        {
            url += $"?version={Uri.EscapeDataString(version)}";
        }
        var response = await _httpClient.DeleteAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return true;
    }

    public async Task<IReadOnlyList<SkillDiscoveryCandidateDto>> SearchDiscoveryAsync(string query, int page = 1, int perPage = 10, CancellationToken cancellationToken = default)
    {
        var url = $"/api/skills/discover/search?q={Uri.EscapeDataString(query)}&page={page}&per_page={perPage}";
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var body = await response.Content.ReadFromJsonAsync<List<SkillDiscoveryCandidateDto>>(JsonOptions, cancellationToken);
        return body ?? new List<SkillDiscoveryCandidateDto>();
    }

    public async Task<SkillDiscoveryCandidateDto> PreviewDiscoveryAsync(string owner, string repo, string branch = "main", string? path = null, CancellationToken cancellationToken = default)
    {
        var url = $"/api/skills/discover/preview?owner={Uri.EscapeDataString(owner)}&repo={Uri.EscapeDataString(repo)}&branch={Uri.EscapeDataString(branch)}";
        if (!string.IsNullOrEmpty(path))
        {
            url += $"&path={Uri.EscapeDataString(path)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<SkillDiscoveryCandidateDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<SkillBundleDto> InstallSkillAsync(InstallSkillRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/skills/install", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<SkillBundleDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<GitHubRateLimitStatusDto> GetGitHubRateLimitAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/skills/discover/rate-limit", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<GitHubRateLimitStatusDto>(JsonOptions, cancellationToken))!;
    }

    // Phase 8: Universal MCP Platform
    public async Task<IReadOnlyList<McpServerRecordDto>> ListMcpServersAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/mcp/servers", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<McpServerRecordDto>>(JsonOptions, cancellationToken))
            ?? new List<McpServerRecordDto>();
    }

    public async Task<McpServerRecordDto> GetMcpServerAsync(string serverId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpServerRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<McpServerRecordDto> RegisterMcpServerAsync(McpServerCreateRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/mcp/servers", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpServerRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<McpServerRecordDto> UpdateMcpServerAsync(string serverId, McpServerUpdateRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PatchAsJsonAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpServerRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<bool> DeleteMcpServerAsync(string serverId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    public async Task<McpServerRecordDto> ApproveMcpServerAsync(string serverId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}/approve", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpServerRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<McpServerRecordDto> ConnectMcpServerAsync(string serverId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}/connect", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpServerRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<McpServerRecordDto> DisconnectMcpServerAsync(string serverId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}/disconnect", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpServerRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<McpPingResponseDto> PingMcpServerAsync(string serverId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/mcp/servers/{Uri.EscapeDataString(serverId)}/ping", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpPingResponseDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<McpVaultItemSummaryDto>> ListMcpVaultSecretsAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/mcp/vault", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<McpVaultItemSummaryDto>>(JsonOptions, cancellationToken))
            ?? new List<McpVaultItemSummaryDto>();
    }

    public async Task<McpVaultItemSummaryDto> WriteMcpVaultSecretAsync(McpVaultWriteRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/mcp/vault", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<McpVaultItemSummaryDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<bool> DeleteMcpVaultSecretAsync(string key, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/mcp/vault/{Uri.EscapeDataString(key)}", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    // Phase 9: Browser and Internet Research
    public async Task<IReadOnlyList<SearchResultDto>> SearchWebAsync(string query, int maxResults = 5, CancellationToken cancellationToken = default)
    {
        var req = new ResearchSearchRequestDto { Query = query, MaxResults = maxResults };
        var response = await _httpClient.PostAsJsonAsync("/api/research/search", req, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<SearchResultDto>>(JsonOptions, cancellationToken))
            ?? new List<SearchResultDto>();
    }

    public async Task<FetchResultDto> FetchWebpageAsync(string url, bool renderJs = false, bool takeScreenshot = false, CancellationToken cancellationToken = default)
    {
        var req = new ResearchFetchRequestDto { Url = url, RenderJs = renderJs, TakeScreenshot = takeScreenshot };
        var response = await _httpClient.PostAsJsonAsync("/api/research/fetch", req, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<FetchResultDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<ResearchEvidenceDto>> ListTaskEvidenceAsync(string taskId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/research/evidence/{Uri.EscapeDataString(taskId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<ResearchEvidenceDto>>(JsonOptions, cancellationToken))
            ?? new List<ResearchEvidenceDto>();
    }

    public async Task<ResearchEvidenceDto> GetEvidenceDetailAsync(string taskId, string evidenceId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/research/evidence/{Uri.EscapeDataString(taskId)}/{Uri.EscapeDataString(evidenceId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<ResearchEvidenceDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<QuarantineItemDto>> ListQuarantinedDownloadsAsync(string taskId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/research/quarantine/{Uri.EscapeDataString(taskId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<QuarantineItemDto>>(JsonOptions, cancellationToken))
            ?? new List<QuarantineItemDto>();
    }

    public async Task<bool> DeleteQuarantinedDownloadAsync(string taskId, string filename, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/research/quarantine/{Uri.EscapeDataString(taskId)}/{Uri.EscapeDataString(filename)}", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    // Phase 10: Generated Tools and Sandbox Platform
    public async Task<ToolValidationReportDto> ValidateToolProposalAsync(GeneratedToolProposalDto proposal, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/sandbox/validate", proposal, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<ToolValidationReportDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<SandboxRunResultDto> RunSandboxTrialAsync(TrialRunRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/sandbox/trial", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<SandboxRunResultDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<SandboxRunResultDto>> ListSandboxEvidenceAsync(int limit = 50, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/sandbox/evidence?limit={limit}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<SandboxRunResultDto>>(JsonOptions, cancellationToken))
            ?? new List<SandboxRunResultDto>();
    }

    public async Task<SandboxRunResultDto> GetSandboxEvidenceAsync(string runId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/sandbox/evidence/{Uri.EscapeDataString(runId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<SandboxRunResultDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<GeneratedToolRecordDto>> ListGeneratedToolsAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/sandbox/tools", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<GeneratedToolRecordDto>>(JsonOptions, cancellationToken))
            ?? new List<GeneratedToolRecordDto>();
    }

    public async Task<GeneratedToolRecordDto> GetGeneratedToolAsync(string toolName, string? version = null, CancellationToken cancellationToken = default)
    {
        var url = string.IsNullOrEmpty(version)
            ? $"/api/sandbox/tools/{Uri.EscapeDataString(toolName)}"
            : $"/api/sandbox/tools/{Uri.EscapeDataString(toolName)}?version={Uri.EscapeDataString(version)}";
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<GeneratedToolRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<string>> ListGeneratedToolVersionsAsync(string toolName, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/sandbox/tools/{Uri.EscapeDataString(toolName)}/versions", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<string>>(JsonOptions, cancellationToken))
            ?? new List<string>();
    }

    public async Task<GeneratedToolRecordDto> PromoteToolAsync(ToolPromotionRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/sandbox/tools/promote", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<GeneratedToolRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<GeneratedToolRecordDto> UpdateGeneratedToolAsync(string toolName, ToolUpdateRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync($"/api/sandbox/tools/{Uri.EscapeDataString(toolName)}/update", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<GeneratedToolRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<bool> DeleteGeneratedToolAsync(string toolName, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/sandbox/tools/{Uri.EscapeDataString(toolName)}", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    // Phase 11: Memory and Persistence Platform
    public async Task<IReadOnlyList<MemoryRecordDto>> ListMemoriesAsync(string? category = null, string? status = null, string? query = null, int limit = 50, CancellationToken cancellationToken = default)
    {
        var url = $"/api/memory/records?limit={limit}";
        if (!string.IsNullOrEmpty(category)) url += $"&category={Uri.EscapeDataString(category)}";
        if (!string.IsNullOrEmpty(status)) url += $"&status={Uri.EscapeDataString(status)}";
        if (!string.IsNullOrEmpty(query)) url += $"&query={Uri.EscapeDataString(query)}";

        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<MemoryRecordDto>>(JsonOptions, cancellationToken))
            ?? new List<MemoryRecordDto>();
    }

    public async Task<MemoryRecordDto> CreateMemoryAsync(MemoryProposalDto proposal, bool autoApprove = false, CancellationToken cancellationToken = default)
    {
        var url = $"/api/memory/records?auto_approve={autoApprove.ToString().ToLowerInvariant()}";
        var response = await _httpClient.PostAsJsonAsync(url, proposal, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<MemoryRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<MemoryRecordDto> GetMemoryAsync(string memoryId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/memory/records/{Uri.EscapeDataString(memoryId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<MemoryRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<MemoryRecordDto> UpdateMemoryAsync(string memoryId, MemoryUpdateRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PatchAsJsonAsync($"/api/memory/records/{Uri.EscapeDataString(memoryId)}", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<MemoryRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<MemoryRecordDto> ApproveMemoryAsync(string memoryId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/memory/records/{Uri.EscapeDataString(memoryId)}/approve", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<MemoryRecordDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<bool> RevokeMemoryAsync(string memoryId, string reason = "Revoked by operator", CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/memory/records/{Uri.EscapeDataString(memoryId)}/revoke?reason={Uri.EscapeDataString(reason)}", null, cancellationToken);
        return response.IsSuccessStatusCode;
    }

    public async Task<bool> DeleteMemoryAsync(string memoryId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/memory/records/{Uri.EscapeDataString(memoryId)}", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    public async Task<IReadOnlyList<MemoryAuditEntryDto>> ListMemoryAuditAsync(string? memoryId = null, int limit = 50, CancellationToken cancellationToken = default)
    {
        var url = $"/api/memory/audit?limit={limit}";
        if (!string.IsNullOrEmpty(memoryId)) url += $"&memory_id={Uri.EscapeDataString(memoryId)}";
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<MemoryAuditEntryDto>>(JsonOptions, cancellationToken))
            ?? new List<MemoryAuditEntryDto>();
    }

    public async Task<MemoryBackupInfoDto> CreateMemoryBackupAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync("/api/memory/backup", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<MemoryBackupInfoDto>(JsonOptions, cancellationToken))!;
    }

    public async Task<IReadOnlyList<MemoryBackupInfoDto>> ListMemoryBackupsAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/memory/backups", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<List<MemoryBackupInfoDto>>(JsonOptions, cancellationToken))
            ?? new List<MemoryBackupInfoDto>();
    }

    public async Task<bool> RestoreMemoryBackupAsync(string backupPath, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/memory/restore?backup_path={Uri.EscapeDataString(backupPath)}", null, cancellationToken);
        return response.IsSuccessStatusCode;
    }

    public async Task<string> ExportMemoriesAsync(string format = "json", CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/memory/export?format={Uri.EscapeDataString(format)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return await response.Content.ReadAsStringAsync(cancellationToken);
    }

    // Phase 12: Desktop Vision and Interaction Platform
    public async Task<IReadOnlyList<WindowSummaryDto>> ListDesktopWindowsAsync(string? query = null, bool includeShielded = false, CancellationToken cancellationToken = default)
    {
        var url = $"/api/desktop/windows?include_shielded={includeShielded.ToString().ToLowerInvariant()}";
        if (!string.IsNullOrWhiteSpace(query))
        {
            url += $"&query={Uri.EscapeDataString(query)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<List<WindowSummaryDto>>(JsonOptions, cancellationToken);
        return result ?? new List<WindowSummaryDto>();
    }

    public async Task<TargetWindowBindingDto> BindDesktopWindowAsync(int hwnd, CancellationToken cancellationToken = default)
    {
        var payload = new { hwnd };
        var response = await _httpClient.PostAsJsonAsync("/api/desktop/bind", payload, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<TargetWindowBindingDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize target window binding.");
    }

    public async Task<TargetWindowBindingDto?> GetActiveDesktopBindingAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync("/api/desktop/binding", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return await response.Content.ReadFromJsonAsync<TargetWindowBindingDto>(JsonOptions, cancellationToken);
    }

    public async Task<bool> ReleaseDesktopBindingAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync("/api/desktop/release", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return true;
    }

    public async Task<UIElementNodeDto> InspectDesktopTreeAsync(int? hwnd = null, int maxDepth = 4, CancellationToken cancellationToken = default)
    {
        var url = $"/api/desktop/tree?max_depth={maxDepth}";
        if (hwnd.HasValue)
        {
            url += $"&hwnd={hwnd.Value}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<UIElementNodeDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize UI tree.");
    }

    public async Task<ScreenshotEvidenceDto> CaptureDesktopWindowAsync(int? hwnd = null, string taskId = "default_task", CancellationToken cancellationToken = default)
    {
        var url = $"/api/desktop/capture?task_id={Uri.EscapeDataString(taskId)}";
        if (hwnd.HasValue)
        {
            url += $"&hwnd={hwnd.Value}";
        }
        var response = await _httpClient.PostAsync(url, null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScreenshotEvidenceDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize screenshot evidence.");
    }

    public async Task<DesktopActionResultDto> ExecuteDesktopActionAsync(DesktopActionRequestDto request, string taskId = "default_task", CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync($"/api/desktop/actions?task_id={Uri.EscapeDataString(taskId)}", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<DesktopActionResultDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize desktop action result.");
    }

    public async Task<bool> TriggerEmergencyStopAsync(string reason = "Operator emergency stop", CancellationToken cancellationToken = default)
    {
        var payload = new { reason };
        var response = await _httpClient.PostAsJsonAsync("/api/desktop/emergency-stop", payload, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return true;
    }

    public async Task<bool> ResetEmergencyStopAsync(CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync("/api/desktop/emergency-stop/reset", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return true;
    }

    public async Task<IReadOnlyList<ScreenshotEvidenceDto>> ListDesktopEvidenceAsync(string? taskId = null, CancellationToken cancellationToken = default)
    {
        var url = "/api/desktop/evidence";
        if (!string.IsNullOrWhiteSpace(taskId))
        {
            url += $"?task_id={Uri.EscapeDataString(taskId)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<List<ScreenshotEvidenceDto>>(JsonOptions, cancellationToken);
        return result ?? new List<ScreenshotEvidenceDto>();
    }

    // Phase 13: Scheduler and Background Work
    public async Task<IReadOnlyList<ScheduleDto>> ListSchedulesAsync(string? status = null, CancellationToken cancellationToken = default)
    {
        var url = "/api/scheduler/schedules";
        if (!string.IsNullOrEmpty(status))
        {
            url += $"?status={Uri.EscapeDataString(status)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<List<ScheduleDto>>(JsonOptions, cancellationToken);
        return result ?? new List<ScheduleDto>();
    }

    public async Task<ScheduleDto> CreateScheduleAsync(ScheduleCreateRequest request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/scheduler/schedules", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScheduleDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize created schedule.");
    }

    public async Task<ScheduleDto> GetScheduleAsync(string scheduleId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/scheduler/schedules/{Uri.EscapeDataString(scheduleId)}", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScheduleDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize schedule.");
    }

    public async Task<ScheduleDto> UpdateScheduleAsync(string scheduleId, ScheduleUpdateRequest request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PatchAsJsonAsync($"/api/scheduler/schedules/{Uri.EscapeDataString(scheduleId)}", request, JsonOptions, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScheduleDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize updated schedule.");
    }

    public async Task<ScheduleDto> PauseScheduleAsync(string scheduleId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/scheduler/schedules/{Uri.EscapeDataString(scheduleId)}/pause", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScheduleDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize paused schedule.");
    }

    public async Task<ScheduleDto> ResumeScheduleAsync(string scheduleId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/scheduler/schedules/{Uri.EscapeDataString(scheduleId)}/resume", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScheduleDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize resumed schedule.");
    }

    public async Task<bool> DeleteScheduleAsync(string scheduleId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/scheduler/schedules/{Uri.EscapeDataString(scheduleId)}", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    public async Task<ScheduleRunDto> TriggerScheduleAsync(string scheduleId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/scheduler/schedules/{Uri.EscapeDataString(scheduleId)}/trigger", null, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<ScheduleRunDto>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Failed to deserialize triggered schedule run.");
    }

    public async Task<IReadOnlyList<ScheduleRunDto>> ListScheduleRunsAsync(string? scheduleId = null, string? status = null, int limit = 50, CancellationToken cancellationToken = default)
    {
        var url = $"/api/scheduler/runs?limit={limit}";
        if (!string.IsNullOrEmpty(scheduleId))
        {
            url += $"&schedule_id={Uri.EscapeDataString(scheduleId)}";
        }
        if (!string.IsNullOrEmpty(status))
        {
            url += $"&status={Uri.EscapeDataString(status)}";
        }
        var response = await _httpClient.GetAsync(url, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        var result = await response.Content.ReadFromJsonAsync<List<ScheduleRunDto>>(JsonOptions, cancellationToken);
        return result ?? new List<ScheduleRunDto>();
    }
}
