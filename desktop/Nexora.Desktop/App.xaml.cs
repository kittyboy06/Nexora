using System;
using System.IO;
using System.Net.Http;
using Microsoft.UI.Xaml;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Nexora.Desktop.Views;

namespace Nexora.Desktop;

public partial class App : Application
{
    public static MainWindow? MainWindowInstance { get; private set; }
    public static CompanionWindow? CompanionWindowInstance { get; private set; }
    public static MainViewModel? MainViewModelInstance { get; private set; }
    private TrayIconService? _trayIconService;
    private BackendSupervisor? _supervisor;

    public App()
    {
        this.InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        var httpClient = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:8000") };
        var apiClient = new NexoraApiClient(httpClient);
        _supervisor = new BackendSupervisor(httpClient);
        var poller = new TaskPoller(apiClient);

        var composer = new TaskComposerViewModel(apiClient);
        var taskDetail = new TaskDetailViewModel(apiClient, poller);
        var approvalDialog = new ApprovalDialogViewModel(apiClient);
        var chat = new ChatViewModel(apiClient);
        var skills = new SkillsViewModel(apiClient);
        var mcp = new McpViewModel(apiClient);

        taskDetail.ApprovalRequested += approval => approvalDialog.SetApproval(approval);

        var mainViewModel = new MainViewModel(apiClient, _supervisor, composer, taskDetail, approvalDialog, chat, skills, mcp);
        MainViewModelInstance = mainViewModel;

        var window = new MainWindow(mainViewModel);
        MainWindowInstance = window;
        window.Activate();

        _trayIconService = new TrayIconService(
            window,
            onShowCompanion: ShowCompanionWindow,
            onExit: ExitApplication
        );
        _trayIconService.Initialize();

        var repoRoot = Directory.GetCurrentDirectory();
        _ = mainViewModel.InitializeAsync(repoRoot);
    }

    public static void ShowCompanionWindow()
    {
        if (MainViewModelInstance == null) return;

        if (CompanionWindowInstance == null)
        {
            CompanionWindowInstance = new CompanionWindow(MainViewModelInstance);
            CompanionWindowInstance.Closed += (s, e) => CompanionWindowInstance = null;
        }
        CompanionWindowInstance.Activate();
    }

    public void ExitApplication()
    {
        _trayIconService?.Dispose();
        _supervisor?.Dispose();
        CompanionWindowInstance?.Close();
        MainWindowInstance?.Close();
        Exit();
    }
}
