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
}
