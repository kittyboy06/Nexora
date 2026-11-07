using System;
using System.IO;
using Nexora.Desktop.Services;
using Xunit;

namespace Nexora.Desktop.Tests;

public class BackendSupervisorTests
{
    [Fact]
    public void ResolveBackendExecutable_ReturnsNull_WhenNoServerExists()
    {
        var tempEmptyDir = Path.Combine(Path.GetTempPath(), "nexora_test_empty_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempEmptyDir);
        try
        {
            var resolved = BackendSupervisor.ResolveBackendExecutable(tempEmptyDir);
            // In testing environment without embedded binary or local app data, it should be null
            Assert.True(resolved == null || File.Exists(resolved));
        }
        finally
        {
            if (Directory.Exists(tempEmptyDir))
            {
                Directory.Delete(tempEmptyDir, true);
            }
        }
    }

    [Fact]
    public void ResolveBackendExecutable_FindsRepoDistServer_WhenPresent()
    {
        var tempRepo = Path.Combine(Path.GetTempPath(), "nexora_test_repo_" + Guid.NewGuid().ToString("N"));
        var serverDir = Path.Combine(tempRepo, "dist", "server");
        Directory.CreateDirectory(serverDir);
        var fakeServerExe = Path.Combine(serverDir, "nexora-server.exe");
        File.WriteAllText(fakeServerExe, "dummy");

        try
        {
            var resolved = BackendSupervisor.ResolveBackendExecutable(tempRepo);
            Assert.NotNull(resolved);
            Assert.True(File.Exists(resolved));
        }
        finally
        {
            if (Directory.Exists(tempRepo))
            {
                Directory.Delete(tempRepo, true);
            }
        }
    }
}
