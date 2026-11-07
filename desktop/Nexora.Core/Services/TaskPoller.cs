using System;
using System.Threading;
using System.Threading.Tasks;
using Nexora.Desktop.Models;
using TaskStatus = Nexora.Desktop.Models.TaskStatus;

namespace Nexora.Desktop.Services;

public class TaskPoller : ITaskPoller
{
    private readonly INexoraApiClient _apiClient;
    private CancellationTokenSource? _cts;
    private readonly object _lock = new();

    public event Action<AgentTask>? TaskUpdated;
    public event Action<AgentTask>? TerminalStateReached;
    public event Action<AgentTask>? ApprovalRequired;

    public bool IsPolling { get; private set; }
    public string? CurrentTaskId { get; private set; }

    public TaskPoller(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    public void StartPolling(string taskId, TimeSpan? interval = null)
    {
        if (string.IsNullOrWhiteSpace(taskId))
        {
            throw new ArgumentException("Task ID cannot be null or empty", nameof(taskId));
        }

        StopPolling();

        lock (_lock)
        {
            _cts = new CancellationTokenSource();
            IsPolling = true;
            CurrentTaskId = taskId;
        }

        var pollInterval = interval ?? TimeSpan.FromMilliseconds(750);
        _ = PollLoopAsync(taskId, pollInterval, _cts.Token);
    }

    public void StopPolling()
    {
        lock (_lock)
        {
            if (!IsPolling)
            {
                return;
            }

            _cts?.Cancel();
            _cts?.Dispose();
            _cts = null;
            IsPolling = false;
            CurrentTaskId = null;
        }
    }

    private async Task PollLoopAsync(string taskId, TimeSpan interval, CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var task = await _apiClient.GetTaskAsync(taskId, cancellationToken);
                TaskUpdated?.Invoke(task);

                if (task.Status == TaskStatus.WAITING_APPROVAL)
                {
                    ApprovalRequired?.Invoke(task);
                }

                if (task.Status is TaskStatus.COMPLETED or TaskStatus.FAILED or TaskStatus.CANCELLED or TaskStatus.INTERRUPTED)
                {
                    TerminalStateReached?.Invoke(task);
                    StopPolling();
                    return;
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch
            {
                // Network transient or retry; continue loop
            }

            try
            {
                await Task.Delay(interval, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    public void Dispose()
    {
        StopPolling();
        GC.SuppressFinalize(this);
    }
}
