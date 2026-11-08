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
    private bool _isChatViewVisible = true;

    [ObservableProperty]
    private bool _isTasksViewVisible;

    [ObservableProperty]
    private bool _isSkillsViewVisible;

    [ObservableProperty]
    private bool _isMcpViewVisible;

    [ObservableProperty]
    private bool _isGeneratedToolsViewVisible;

    [ObservableProperty]
    private bool _isMemoryViewVisible;

    [ObservableProperty]
    private bool _isDesktopVisionViewVisible;

    [ObservableProperty]
    private bool _isSchedulerViewVisible;

    [ObservableProperty]
    private string _activeModel = "None";

    [ObservableProperty]
    private AppThemeMode _currentThemeMode = AppThemeMode.SystemDefault;

    public event Action<AppThemeMode>? ThemeChanged;

    partial void OnCurrentThemeModeChanged(AppThemeMode value)
    {
        ThemeChanged?.Invoke(value);
    }

    [RelayCommand]
    public void SetTheme(string mode)
    {
        CurrentThemeMode = mode?.ToLowerInvariant() switch
        {
            "light" => AppThemeMode.Light,
            "dark" => AppThemeMode.Dark,
            _ => AppThemeMode.SystemDefault
        };
    }

    [ObservableProperty]
    private string _selectedModel = string.Empty;

    public ObservableCollection<string> InstalledModels { get; } = new();

    private bool _isSyncingModel;

    [ObservableProperty]
    private string _statusMessage = "Initializing...";

    public TaskComposerViewModel Composer { get; }
    public TaskDetailViewModel TaskDetail { get; }
    public ApprovalDialogViewModel ApprovalDialog { get; }
    public ChatViewModel Chat { get; }
    public SkillsViewModel Skills { get; }
    public McpViewModel Mcp { get; }
    public GeneratedToolsViewModel GeneratedTools { get; }
    public MemoryViewModel Memory { get; }
    public DesktopVisionViewModel DesktopVision { get; }
    public SchedulerViewModel Scheduler { get; }

    public ObservableCollection<AgentTask> RecentTasks { get; } = new();

    public MainViewModel(
        INexoraApiClient apiClient,
        IBackendSupervisor supervisor,
        TaskComposerViewModel composer,
        TaskDetailViewModel taskDetail,
        ApprovalDialogViewModel approvalDialog,
        ChatViewModel? chat = null,
        SkillsViewModel? skills = null,
        McpViewModel? mcp = null,
        GeneratedToolsViewModel? generatedTools = null,
        MemoryViewModel? memory = null,
        DesktopVisionViewModel? desktopVision = null,
        SchedulerViewModel? scheduler = null)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
        _supervisor = supervisor ?? throw new ArgumentNullException(nameof(supervisor));
        Composer = composer ?? throw new ArgumentNullException(nameof(composer));
        TaskDetail = taskDetail ?? throw new ArgumentNullException(nameof(taskDetail));
        ApprovalDialog = approvalDialog ?? throw new ArgumentNullException(nameof(approvalDialog));
        Chat = chat ?? new ChatViewModel(_apiClient);
        Skills = skills ?? new SkillsViewModel(_apiClient);
        Mcp = mcp ?? new McpViewModel(_apiClient);
        GeneratedTools = generatedTools ?? new GeneratedToolsViewModel(_apiClient);
        Memory = memory ?? new MemoryViewModel(_apiClient);
        DesktopVision = desktopVision ?? new DesktopVisionViewModel(_apiClient);
        Scheduler = scheduler ?? new SchedulerViewModel(_apiClient);

        Composer.TaskCreated += OnTaskCreated;
        ApprovalDialog.DecisionCompleted += OnApprovalDecided;
        Chat.WorkItemNavigationRequested += OnWorkItemNavigationRequested;
    }

    [RelayCommand]
    public void ShowChatView()
    {
        IsChatViewVisible = true;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowTasksView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = true;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowSkillsView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = true;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowMcpView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = true;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowGeneratedToolsView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = true;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowMemoryView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = true;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowDesktopVisionView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = true;
        IsSchedulerViewVisible = false;
    }

    [RelayCommand]
    public void ShowSchedulerView()
    {
        IsChatViewVisible = false;
        IsTasksViewVisible = false;
        IsSkillsViewVisible = false;
        IsMcpViewVisible = false;
        IsGeneratedToolsViewVisible = false;
        IsMemoryViewVisible = false;
        IsDesktopVisionViewVisible = false;
        IsSchedulerViewVisible = true;
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
                await Chat.LoadConversationsAsync();
                await Composer.LoadProfilesAsync();
                await LoadRecentTasksAsync();
                await Skills.LoadInstalledSkillsAsync();
                await Mcp.LoadServersAsync();
                await Mcp.LoadVaultSecretsAsync();
                await GeneratedTools.LoadAllAsync();
                await Memory.LoadAllAsync();
                await Scheduler.LoadSchedulesAsync();
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
            ActiveModel = !string.IsNullOrWhiteSpace(ollama.ConfiguredModel) ? ollama.ConfiguredModel : "auto";

            InstalledModels.Clear();
            if (ollama.InstalledModels != null)
            {
                foreach (var model in ollama.InstalledModels)
                {
                    InstalledModels.Add(model);
                }
            }

            _isSyncingModel = true;
            try
            {
                if (!string.IsNullOrEmpty(ActiveModel) && InstalledModels.Contains(ActiveModel))
                {
                    if (SelectedModel != ActiveModel)
                    {
                        SelectedModel = ActiveModel;
                    }
                }
                else if (InstalledModels.Count > 0 && string.IsNullOrEmpty(SelectedModel))
                {
                    SelectedModel = InstalledModels[0];
                }
            }
            finally
            {
                _isSyncingModel = false;
            }
        }
        catch
        {
            StatusMessage = "Backend unreachable.";
            IsBackendOnline = false;
            IsOllamaOnline = false;
        }
    }

    async partial void OnSelectedModelChanged(string value)
    {
        if (_isSyncingModel || string.IsNullOrWhiteSpace(value) || value == ActiveModel)
        {
            return;
        }

        try
        {
            StatusMessage = $"Switching active model to {value}...";
            var success = await _apiClient.SetActiveModelAsync(value);
            if (success)
            {
                ActiveModel = value;
                StatusMessage = $"Active model set to {value}";
                await Composer.LoadProfilesAsync();
            }
            else
            {
                StatusMessage = $"Failed to switch model to {value}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error switching model: {ex.Message}";
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

    private async void OnWorkItemNavigationRequested(ConversationWorkItem item)
    {
        switch (item.Intent)
        {
            case WorkItemIntent.Task:
            case WorkItemIntent.Research:
                ShowTasksView();
                if (!string.IsNullOrEmpty(item.TargetId))
                {
                    try
                    {
                        var task = await _apiClient.GetTaskAsync(item.TargetId);
                        if (task != null)
                        {
                            TaskDetail.LoadTask(task);
                        }
                    }
                    catch
                    {
                        // Ignore lookup error if task is pending or not created yet
                    }
                }
                break;
            case WorkItemIntent.SkillImport:
                ShowSkillsView();
                break;
            case WorkItemIntent.McpOnboard:
                ShowMcpView();
                break;
            case WorkItemIntent.DesktopVision:
                ShowDesktopVisionView();
                break;
            case WorkItemIntent.Schedule:
                ShowSchedulerView();
                break;
            default:
                ShowTasksView();
                break;
        }
    }
}
