using System;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class ThemeAndConverterTests
{
    private readonly MainViewModel _mainVm;

    public ThemeAndConverterTests()
    {
        var mockApiClient = new Mock<INexoraApiClient>();
        var mockSupervisor = new Mock<IBackendSupervisor>();
        var mockPoller = new Mock<ITaskPoller>();

        var composer = new TaskComposerViewModel(mockApiClient.Object);
        var taskDetail = new TaskDetailViewModel(mockApiClient.Object, mockPoller.Object);
        var approvalDialog = new ApprovalDialogViewModel(mockApiClient.Object);

        _mainVm = new MainViewModel(
            mockApiClient.Object,
            mockSupervisor.Object,
            composer,
            taskDetail,
            approvalDialog
        );
    }

    [Fact]
    public void SetTheme_Light_UpdatesPropertyAndFiresEvent()
    {
        AppThemeMode? receivedMode = null;
        _mainVm.ThemeChanged += mode => receivedMode = mode;

        _mainVm.SetTheme("light");

        Assert.Equal(AppThemeMode.Light, _mainVm.CurrentThemeMode);
        Assert.Equal(AppThemeMode.Light, receivedMode);
    }

    [Fact]
    public void SetTheme_Dark_UpdatesPropertyAndFiresEvent()
    {
        AppThemeMode? receivedMode = null;
        _mainVm.ThemeChanged += mode => receivedMode = mode;

        _mainVm.SetTheme("dark");

        Assert.Equal(AppThemeMode.Dark, _mainVm.CurrentThemeMode);
        Assert.Equal(AppThemeMode.Dark, receivedMode);
    }

    [Fact]
    public void SetTheme_System_UpdatesPropertyAndFiresEvent()
    {
        _mainVm.SetTheme("dark");

        AppThemeMode? receivedMode = null;
        _mainVm.ThemeChanged += mode => receivedMode = mode;

        _mainVm.SetTheme("system");

        Assert.Equal(AppThemeMode.SystemDefault, _mainVm.CurrentThemeMode);
        Assert.Equal(AppThemeMode.SystemDefault, receivedMode);
    }

    [Theory]
    [InlineData(AppThemeMode.SystemDefault, 0)]
    [InlineData(AppThemeMode.Light, 1)]
    [InlineData(AppThemeMode.Dark, 2)]
    public void AppThemeMode_EnumValues_MatchExpected(AppThemeMode mode, int expectedValue)
    {
        Assert.Equal(expectedValue, (int)mode);
    }
}
