using System;
using System.Runtime.CompilerServices;

namespace Nexora.Desktop;

internal static class StartupInitializer
{
    [ModuleInitializer]
    internal static void Initialize()
    {
        Environment.SetEnvironmentVariable("MICROSOFT_WINDOWSAPPRUNTIME_BASE_DIRECTORY", AppContext.BaseDirectory);
    }
}
