using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;

namespace Nexora.Desktop.Services;

public class BackendSupervisor : IBackendSupervisor
{
    private readonly HttpClient _httpClient;
    private Process? _backendProcess;
    private readonly object _lock = new();
    private IntPtr _jobHandle = IntPtr.Zero;

    public bool IsManagedProcessRunning => _backendProcess is { HasExited: false };
    public int? ProcessId => IsManagedProcessRunning ? _backendProcess?.Id : null;

    #region Win32 Job Object Interop
    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryLimit;
        public UIntPtr PeakJobMemoryLimit;
    }

    private const int JobObjectExtendedLimitInformation = 9;
    private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? lpName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr hJob, int JobObjectInfoClass, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    private void BindProcessToJobObject(IntPtr processHandle)
    {
        if (!OperatingSystem.IsWindows() || processHandle == IntPtr.Zero) return;

        try
        {
            if (_jobHandle == IntPtr.Zero)
            {
                _jobHandle = CreateJobObject(IntPtr.Zero, null);
                if (_jobHandle != IntPtr.Zero)
                {
                    var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

                    var length = (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
                    var ptr = Marshal.AllocHGlobal((int)length);
                    try
                    {
                        Marshal.StructureToPtr(info, ptr, false);
                        SetInformationJobObject(_jobHandle, JobObjectExtendedLimitInformation, ptr, length);
                    }
                    finally
                    {
                        Marshal.FreeHGlobal(ptr);
                    }
                }
            }

            if (_jobHandle != IntPtr.Zero)
            {
                AssignProcessToJobObject(_jobHandle, processHandle);
            }
        }
        catch
        {
            // Fallback gracefully if Job Object API is restricted
        }
    }
    #endregion

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

        // 2. Launch child process (bundled executable or local dev python)
        lock (_lock)
        {
            if (IsManagedProcessRunning)
            {
                StopBackend();
            }

            var serverExe = ResolveBackendExecutable(repoRoot);
            ProcessStartInfo startInfo;

            if (!string.IsNullOrEmpty(serverExe))
            {
                startInfo = new ProcessStartInfo
                {
                    FileName = serverExe,
                    Arguments = "--host 127.0.0.1 --port 8000",
                    WorkingDirectory = Path.GetDirectoryName(serverExe) ?? repoRoot,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };
            }
            else
            {
                startInfo = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
                    WorkingDirectory = repoRoot,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };
            }

            try
            {
                _backendProcess = Process.Start(startInfo);
                if (_backendProcess == null)
                {
                    throw new InvalidOperationException("Backend process did not start.");
                }

                BindProcessToJobObject(_backendProcess.Handle);

                _ = DrainStreamAsync(_backendProcess.StandardOutput);
                _ = DrainStreamAsync(_backendProcess.StandardError);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"Failed to launch backend process: {ex.Message}", ex);
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

    private static async Task DrainStreamAsync(StreamReader stream)
    {
        try
        {
            while (await stream.ReadLineAsync() != null)
            {
                // Keep redirected pipes from blocking the backend process.
            }
        }
        catch (ObjectDisposedException)
        {
            // Expected when the supervisor stops the process.
        }
        catch (IOException)
        {
            // Expected when the child exits while its stream is being drained.
        }
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

            if (_jobHandle != IntPtr.Zero)
            {
                try
                {
                    CloseHandle(_jobHandle);
                }
                catch
                {
                    // Ignore handle cleanup errors
                }
                finally
                {
                    _jobHandle = IntPtr.Zero;
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

    public static string? ResolveBackendExecutable(string repoRoot)
    {
        // 1. Check embedded resource extraction in LocalAppData
        var localAppDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Nexora", "bin");
        var localAppBinary = Path.Combine(localAppDir, "nexora-server.exe");

        TryExtractEmbeddedServer(localAppBinary);

        if (File.Exists(localAppBinary))
        {
            return localAppBinary;
        }

        // 2. Check current base directory
        var baseDir = AppDomain.CurrentDomain.BaseDirectory;
        var directBinary = Path.Combine(baseDir, "nexora-server.exe");
        if (File.Exists(directBinary)) return directBinary;

        var subDirBinary = Path.Combine(baseDir, "server", "nexora-server.exe");
        if (File.Exists(subDirBinary)) return subDirBinary;

        // 3. Check workspace repo dist/server
        if (!string.IsNullOrEmpty(repoRoot))
        {
            var repoBinary = Path.Combine(repoRoot, "dist", "server", "nexora-server.exe");
            if (File.Exists(repoBinary)) return repoBinary;
        }

        return null;
    }

    private static void TryExtractEmbeddedServer(string targetPath)
    {
        try
        {
            var assemblies = new[]
            {
                Assembly.GetEntryAssembly(),
                typeof(BackendSupervisor).Assembly,
                Assembly.GetExecutingAssembly(),
            };

            Stream? stream = null;
            foreach (var asm in assemblies)
            {
                if (asm == null) continue;
                var resNames = asm.GetManifestResourceNames();
                var match = Array.Find(resNames, r => r.Equals("nexora-server.exe", StringComparison.OrdinalIgnoreCase) ||
                                                      r.EndsWith(".nexora-server.exe", StringComparison.OrdinalIgnoreCase) ||
                                                      r.EndsWith("nexora-server.exe", StringComparison.OrdinalIgnoreCase));
                if (match != null)
                {
                    stream = asm.GetManifestResourceStream(match);
                    if (stream != null) break;
                }
            }

            if (stream == null) return;
            using (stream)
            {
                var targetDir = Path.GetDirectoryName(targetPath);
                if (!string.IsNullOrEmpty(targetDir) && !Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                if (!File.Exists(targetPath) || new FileInfo(targetPath).Length != stream.Length)
                {
                    using var fs = new FileStream(targetPath, FileMode.Create, FileAccess.Write, FileShare.None);
                    stream.CopyTo(fs);
                }
            }
        }
        catch
        {
            // Non-fatal if embedded resource is missing or extraction fails in dev mode
        }
    }
}
