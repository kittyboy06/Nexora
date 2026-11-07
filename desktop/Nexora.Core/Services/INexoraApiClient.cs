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
    Task<AgentTask> CreateTaskAsync(string prompt, string? profileId = null, CancellationToken cancellationToken = default);
    Task<AgentTask> GetTaskAsync(string taskId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<AgentTask>> ListTasksAsync(CancellationToken cancellationToken = default);
    Task<AgentTask> CancelTaskAsync(string taskId, CancellationToken cancellationToken = default);
    Task<AgentTask> DecideApprovalAsync(string taskId, string approvalId, bool approved, CancellationToken cancellationToken = default);
}
