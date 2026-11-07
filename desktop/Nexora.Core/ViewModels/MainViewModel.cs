using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class MainViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;
    private readonly IBackendSupervisor _supervisor;

    [ObservableProperty]
    private bool _isBackendOnline;

    [ObservableProperty]
    private bool _isOllamaOnline;

    [ObservableProperty]
    private bool _isTasksViewVisible = true;

    [ObservableProperty]
    private bool _isSkillsViewVisible;

    [ObservableProperty]
    private bool _isMcpViewVisible;

    [ObservableProperty]
    private string _activeModel = "None";

    [ObservableProperty]
    private string _statusMessage = "Initializing...";

    public TaskComposerViewModel Composer { get; }
    public TaskDetailViewModel TaskDetail { get; }
    public ApprovalDialogViewModel ApprovalDialog { get; }
    public SkillsViewModel Skills { get; }
    public McpViewModel Mcp { get; }

    public ObservableCollection<AgentTask> RecentTasks { get; } = new();

    public MainViewModel(
        INexoraApiClient apiClient,
        IBackendSupervisor supervisor,
        TaskComposerViewModel composer,
        TaskDetailViewModel taskDetail,
        ApprovalDialogViewModel approvalDialog,
        SkillsViewModel? skills = null,
        McpViewModel? mcp = null)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
        _supervisor = supervisor ?? throw new ArgumentNullException(nameof(supervisor));
        Composer = composer ?? throw new ArgumentNullException(nameof(composer));
        TaskDetail = taskDetail ?? throw new ArgumentNullException(nameof(taskDetail));
        ApprovalDialog = approvalDialog ?? throw new ArgumentNullException(nameof(approvalDialog));
        Skills = skills ?? new SkillsViewModel(_apiClient);
        Mcp = mcp ?? new McpViewModel(_apiClient);

        Composer.TaskCreated += OnTaskCreated;
        ApprovalDialog.DecisionCompleted += OnApprovalDecided;
    }

    [RelayCommand]
    public void ShowTasksView()
    {
        IsTasksViewVisible = true;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
    }

    [RelayCommand]
    public void ShowSkillsView()
    {
        IsTasksViewVisible = false;
        IsSkillsViewVisible = true;
        IsMcpViewVisible = false;
    }

    [RelayCommand]
    public void ShowMcpView()
    {
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = true;
    }

    public async Task InitializeAsync(string repoRoot)
    {
        StatusMessage = "Connecting to NEXORA backend...";
        try
        {
            IsBackendOnline = await _supervisor.EnsureBackendRunningAsync(repoRoot);
            if (IsBackendOnline)
            {
                StatusMessage = "Backend connected. Checking Ollama...";
                await RefreshStatusAsync();
                await Composer.LoadProfilesAsync();
                await LoadRecentTasksAsync();
                await Skills.LoadInstalledSkillsAsync();
                await Mcp.LoadServersAsync();
                await Mcp.LoadVaultSecretsAsync();
                StatusMessage = "Ready";
            }
            else
            {
                StatusMessage = "Failed to reach backend service.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Initialization error: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task RefreshStatusAsync()
    {
        try
        {
            var health = await _apiClient.GetHealthAsync();
            IsBackendOnline = health.Status == "ok";

            var ollama = await _apiClient.GetOllamaStatusAsync();
            IsOllamaOnline = ollama.Reachable;
            ActiveModel = ollama.ConfiguredModel;
        }
        catch
        {
            StatusMessage = "Backend unreachable.";
            IsBackendOnline = false;
            IsOllamaOnline = false;
        }
    }

    [RelayCommand]
    public async Task LoadRecentTasksAsync()
    {
        try
        {
            var tasks = await _apiClient.ListTasksAsync();
            RecentTasks.Clear();
            foreach (var t in tasks)
            {
                RecentTasks.Add(t);
            }
        }
        catch
        {
            // Ignore background load error
        }
    }

    private void OnTaskCreated(AgentTask task)
    {
        RecentTasks.Insert(0, task);
        TaskDetail.LoadTask(task);
    }

    private void OnApprovalDecided(AgentTask task)
    {
        TaskDetail.LoadTask(task);
    }
}
