using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class DesktopVisionViewModelTests
{
    [Fact]
    public async Task LoadWindowsAsync_PopulatesWindowsAndActiveBinding()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var windows = new List<WindowSummaryDto>
        {
            new() { Hwnd = 1001, ProcessName = "notepad.exe", WindowTitle = "Untitled - Notepad" },
            new() { Hwnd = 1002, ProcessName = "calc.exe", WindowTitle = "Calculator" },
        };
        var activeBinding = new TargetWindowBindingDto
        {
            Hwnd = 1001,
            ProcessName = "notepad.exe",
            WindowTitle = "Untitled - Notepad",
        };

        mockClient
            .Setup(c => c.ListDesktopWindowsAsync(It.IsAny<string?>(), false, It.IsAny<CancellationToken>()))
            .ReturnsAsync(windows);
        mockClient
            .Setup(c => c.GetActiveDesktopBindingAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(activeBinding);

        var vm = new DesktopVisionViewModel(mockClient.Object);
        await vm.LoadWindowsCommand.ExecuteAsync(null);

        Assert.Equal(2, vm.Windows.Count);
        Assert.NotNull(vm.ActiveBinding);
        Assert.Equal(1001, vm.ActiveBinding.Hwnd);
        Assert.Contains("Discovered 2 desktop windows", vm.StatusMessage);
    }

    [Fact]
    public async Task BindWindowAsync_CallsApiAndLoadsTreeAndCapture()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var targetWindow = new WindowSummaryDto { Hwnd = 1001, ProcessName = "notepad.exe", WindowTitle = "Notepad" };
        var binding = new TargetWindowBindingDto { Hwnd = 1001, ProcessName = "notepad.exe", WindowTitle = "Notepad" };
        var tree = new UIElementNodeDto
        {
            ElementId = "elem_root",
            AutomationId = "RootWin",
            Name = "Notepad",
            ControlType = "Window",
            Children = new List<UIElementNodeDto>
            {
                new() { ElementId = "elem_edit", AutomationId = "EditBox", Name = "Editor", ControlType = "Edit" },
            },
        };
        var screenshot = new ScreenshotEvidenceDto
        {
            ImageId = "snap_abc123",
            Width = 800,
            Height = 600,
            IsRedacted = false,
            FilePath = "quarantine/snap_abc123.png",
        };

        mockClient
            .Setup(c => c.BindDesktopWindowAsync(1001, It.IsAny<CancellationToken>()))
            .ReturnsAsync(binding);
        mockClient
            .Setup(c => c.InspectDesktopTreeAsync(1001, 4, It.IsAny<CancellationToken>()))
            .ReturnsAsync(tree);
        mockClient
            .Setup(c => c.CaptureDesktopWindowAsync(1001, "default_task", It.IsAny<CancellationToken>()))
            .ReturnsAsync(screenshot);
        mockClient
            .Setup(c => c.ListDesktopEvidenceAsync(It.IsAny<string?>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ScreenshotEvidenceDto> { screenshot });

        var vm = new DesktopVisionViewModel(mockClient.Object);
        await vm.BindWindowCommand.ExecuteAsync(targetWindow);

        Assert.NotNull(vm.ActiveBinding);
        Assert.Equal(1001, vm.ActiveBinding.Hwnd);
        Assert.Equal(2, vm.FlattenedElements.Count); // Root + 1 child
        Assert.NotNull(vm.LatestScreenshot);
        Assert.Equal("snap_abc123", vm.LatestScreenshot.ImageId);
        Assert.Contains("Captured 800x600 frame", vm.StatusMessage);
    }

    [Fact]
    public async Task ReleaseBindingAsync_ClearsActiveBindingAndTree()
    {
        var mockClient = new Mock<INexoraApiClient>();
        mockClient
            .Setup(c => c.ReleaseDesktopBindingAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var vm = new DesktopVisionViewModel(mockClient.Object)
        {
            ActiveBinding = new TargetWindowBindingDto { Hwnd = 1001 },
            ActiveTree = new UIElementNodeDto { ElementId = "elem_1" },
        };
        vm.FlattenedElements.Add(new UIElementNodeDto { ElementId = "elem_1" });

        await vm.ReleaseBindingCommand.ExecuteAsync(null);

        Assert.Null(vm.ActiveBinding);
        Assert.Null(vm.ActiveTree);
        Assert.Empty(vm.FlattenedElements);
        Assert.Equal("Active window binding released.", vm.StatusMessage);
    }

    [Fact]
    public async Task ExecuteActionAsync_DispatchesRequestAndUpdatesResult()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var binding = new TargetWindowBindingDto { Hwnd = 1001, ProcessName = "notepad.exe", WindowTitle = "Notepad" };
        var actionResult = new DesktopActionResultDto
        {
            ActionId = "act_101",
            ActionType = "type_text",
            Status = "SUCCESS",
            Message = "Text typed and verified.",
            VerificationOk = true,
        };
        var tree = new UIElementNodeDto { ElementId = "elem_root", Children = new List<UIElementNodeDto>() };

        mockClient
            .Setup(c => c.ExecuteDesktopActionAsync(It.IsAny<DesktopActionRequestDto>(), "default_task", It.IsAny<CancellationToken>()))
            .ReturnsAsync(actionResult);
        mockClient
            .Setup(c => c.InspectDesktopTreeAsync(1001, 4, It.IsAny<CancellationToken>()))
            .ReturnsAsync(tree);
        mockClient
            .Setup(c => c.ListDesktopEvidenceAsync(It.IsAny<string?>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ScreenshotEvidenceDto>());

        var vm = new DesktopVisionViewModel(mockClient.Object)
        {
            ActiveBinding = binding,
            SelectedActionType = "type_text",
            TargetElementId = "elem_notepad_editor",
            TextInput = "Hello from WinUI 3",
            ExpectedPostcondition = "text_contains:Hello",
        };

        await vm.ExecuteActionCommand.ExecuteAsync(null);

        Assert.NotNull(vm.LastActionResult);
        Assert.Equal("SUCCESS", vm.LastActionResult.Status);
        Assert.True(vm.LastActionResult.VerificationOk);
        Assert.Contains("Action SUCCESS: Text typed and verified.", vm.StatusMessage);
    }

    [Fact]
    public async Task EmergencyStop_TriggerAndReset_UpdatesState()
    {
        var mockClient = new Mock<INexoraApiClient>();
        mockClient
            .Setup(c => c.TriggerEmergencyStopAsync(It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        mockClient
            .Setup(c => c.ResetEmergencyStopAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var vm = new DesktopVisionViewModel(mockClient.Object);

        // 1. Trigger
        await vm.TriggerEmergencyStopCommand.ExecuteAsync("Test stop");
        Assert.True(vm.IsEmergencyStopActive);
        Assert.Contains("EMERGENCY STOP ACTIVE", vm.StatusMessage);

        // 2. Action blocked while stopped
        vm.ActiveBinding = new TargetWindowBindingDto { Hwnd = 1001 };
        await vm.ExecuteActionCommand.ExecuteAsync(null);
        Assert.Contains("Blocked: Emergency stop is actively engaged.", vm.StatusMessage);

        // 3. Reset
        await vm.ResetEmergencyStopCommand.ExecuteAsync(null);
        Assert.False(vm.IsEmergencyStopActive);
        Assert.Contains("Emergency stop reset", vm.StatusMessage);
    }

    [Fact]
    public async Task StartAutonomyAsync_ValidConfig_InitializesSession()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sessionState = new AutonomousSessionStateDto
        {
            SessionId = "sess_test1",
            Goal = "Automate calculator sum",
            Status = "RUNNING",
            ActionCount = 0,
            MaxActions = 15,
            MaxDurationSeconds = 300.0,
            LastActionMessage = "Session initialized.",
        };

        mockClient
            .Setup(c => c.StartAutonomousSessionAsync(It.IsAny<AutonomousSessionConfigDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(sessionState);

        var vm = new DesktopVisionViewModel(mockClient.Object)
        {
            AutonomyGoal = "Automate calculator sum",
            AutonomyMaxActions = 15,
            AutonomyMaxDurationSeconds = 300.0,
        };

        await vm.StartAutonomyCommand.ExecuteAsync(null);

        Assert.NotNull(vm.ActiveAutonomySession);
        Assert.Equal("sess_test1", vm.ActiveAutonomySession.SessionId);
        Assert.True(vm.IsAutonomyRunning);
        Assert.False(vm.IsAutonomyPaused);
        Assert.Equal("RUNNING", vm.AutonomyStatusText);
        Assert.Contains("Autonomous session sess_test1 initialized", vm.StatusMessage);
    }

    [Fact]
    public async Task StepAutonomyAsync_AdvancesSessionAndUpdatesBudget()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var stepResult = new AutonomousStepResultDto
        {
            SessionId = "sess_step1",
            StepNumber = 1,
            IsTerminal = false,
            ActionResult = new DesktopActionResultDto
            {
                ActionId = "act_1",
                Status = "SUCCESS",
                Message = "Clicked element 42",
            },
            SessionState = new AutonomousSessionStateDto
            {
                SessionId = "sess_step1",
                Status = "RUNNING",
                ActionCount = 1,
                MaxActions = 5,
            },
        };

        mockClient
            .Setup(c => c.ExecuteAutonomousStepAsync("sess_step1", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(stepResult);
        mockClient
            .Setup(c => c.ListDesktopEvidenceAsync(It.IsAny<string?>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ScreenshotEvidenceDto>());

        var vm = new DesktopVisionViewModel(mockClient.Object)
        {
            ActiveAutonomySession = new AutonomousSessionStateDto { SessionId = "sess_step1", Status = "RUNNING" },
            IsAutonomyRunning = true,
        };

        await vm.StepAutonomyCommand.ExecuteAsync(null);

        Assert.Equal(1, vm.ActiveAutonomySession.ActionCount);
        Assert.Equal("RUNNING", vm.AutonomyStatusText);
        Assert.Contains("Step 1: Clicked element 42", vm.StatusMessage);
    }

    [Fact]
    public async Task PauseResumeStopAutonomyAsync_UpdatesSessionStatus()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var pausedState = new AutonomousSessionStateDto { SessionId = "sess_1", Status = "PAUSED" };
        var resumedState = new AutonomousSessionStateDto { SessionId = "sess_1", Status = "RUNNING" };
        var stoppedState = new AutonomousSessionStateDto { SessionId = "sess_1", Status = "STOPPED" };

        mockClient.Setup(c => c.PauseAutonomousSessionAsync("sess_1", It.IsAny<CancellationToken>())).ReturnsAsync(pausedState);
        mockClient.Setup(c => c.ResumeAutonomousSessionAsync("sess_1", It.IsAny<CancellationToken>())).ReturnsAsync(resumedState);
        mockClient.Setup(c => c.StopAutonomousSessionAsync("sess_1", "Stopped by operator", It.IsAny<CancellationToken>())).ReturnsAsync(stoppedState);

        var vm = new DesktopVisionViewModel(mockClient.Object)
        {
            ActiveAutonomySession = new AutonomousSessionStateDto { SessionId = "sess_1", Status = "RUNNING" },
            IsAutonomyRunning = true,
        };

        // Pause
        await vm.PauseAutonomyCommand.ExecuteAsync(null);
        Assert.True(vm.IsAutonomyPaused);
        Assert.Equal("PAUSED", vm.AutonomyStatusText);

        // Resume
        await vm.ResumeAutonomyCommand.ExecuteAsync(null);
        Assert.False(vm.IsAutonomyPaused);
        Assert.Equal("RUNNING", vm.AutonomyStatusText);

        // Stop
        await vm.StopAutonomyCommand.ExecuteAsync(null);
        Assert.False(vm.IsAutonomyRunning);
        Assert.Equal("STOPPED", vm.AutonomyStatusText);
    }
}
