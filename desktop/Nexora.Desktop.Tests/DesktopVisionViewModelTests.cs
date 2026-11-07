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
}
