using System;
using Nexora.Desktop.Models;

namespace Nexora.Desktop.Services;

public interface ITaskPoller : IDisposable
{
    event Action<AgentTask>? TaskUpdated;
    event Action<AgentTask>? TerminalStateReached;
    event Action<AgentTask>? ApprovalRequired;

    bool IsPolling { get; }
    string? CurrentTaskId { get; }

    void StartPolling(string taskId, TimeSpan? interval = null);
    void StopPolling();
}
