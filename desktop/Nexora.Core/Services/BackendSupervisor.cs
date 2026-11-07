using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace Nexora.Desktop.Services;

public class BackendSupervisor : IBackendSupervisor
{
    private readonly HttpClient _httpClient;
    private Process? _backendProcess;
    private readonly object _lock = new();

    public bool IsManagedProcessRunning => _backendProcess is { HasExited: false };
    public int? ProcessId => IsManagedProcessRunning ? _backendProcess?.Id : null;

    public BackendSupervisor(HttpClient? httpClient = null)
    {
        _httpClient = httpClient ?? new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
    }

    public async Task<bool> EnsureBackendRunningAsync(string repoRoot, CancellationToken cancellationToken = default)
    {
        // 1. Check if backend is already running on port 8000
        if (await ProbeHealthAsync(cancellationToken))
        {
            return true;
        }

        // 2. Launch uvicorn child process
        lock (_lock)
        {
            if (IsManagedProcessRunning)
            {
                return true;
            }

            var startInfo = new ProcessStartInfo
            {
                FileName = "python",
                Arguments = "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
                WorkingDirectory = repoRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };

            try
            {
                _backendProcess = Process.Start(startInfo);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"Failed to launch Python backend process: {ex.Message}", ex);
            }
        }

        // 3. Poll health up to 10 seconds
        var timeout = DateTime.UtcNow.AddSeconds(10);
        while (DateTime.UtcNow < timeout && !cancellationToken.IsCancellationRequested)
        {
            if (await ProbeHealthAsync(cancellationToken))
            {
                return true;
            }

            await Task.Delay(250, cancellationToken);
        }

        return false;
    }

    private async Task<bool> ProbeHealthAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await _httpClient.GetAsync("http://127.0.0.1:8000/api/health", cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public void StopBackend()
    {
        lock (_lock)
        {
            if (_backendProcess is { HasExited: false })
            {
                try
                {
                    _backendProcess.Kill(entireProcessTree: true);
                    _backendProcess.WaitForExit(3000);
                }
                catch
                {
                    // Ignore shutdown errors
                }
                finally
                {
                    _backendProcess.Dispose();
                    _backendProcess = null;
                }
            }
        }
    }

    public void Dispose()
    {
        StopBackend();
        _httpClient.Dispose();
        GC.SuppressFinalize(this);
    }
}
