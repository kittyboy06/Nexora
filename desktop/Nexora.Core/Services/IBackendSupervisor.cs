using System;
using System.Threading;
using System.Threading.Tasks;

namespace Nexora.Desktop.Services;

public interface IBackendSupervisor : IDisposable
{
    bool IsManagedProcessRunning { get; }
    int? ProcessId { get; }

    Task<bool> EnsureBackendRunningAsync(string repoRoot, CancellationToken cancellationToken = default);
    void StopBackend();
}
