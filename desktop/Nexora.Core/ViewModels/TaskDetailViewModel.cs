using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using TaskStatus = Nexora.Desktop.Models.TaskStatus;

namespace Nexora.Desktop.ViewModels;

public partial class TaskDetailViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;
    private readonly ITaskPoller _taskPoller;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasCurrentTask))]
    [NotifyPropertyChangedFor(nameof(CurrentTaskId))]
    [NotifyPropertyChangedFor(nameof(CurrentTaskStatus))]
    [NotifyPropertyChangedFor(nameof(CurrentTaskPrompt))]
    [NotifyPropertyChangedFor(nameof(CurrentTaskRouting))]
    [NotifyPropertyChangedFor(nameof(CurrentTaskSteps))]
    [NotifyPropertyChangedFor(nameof(CanCancel))]
    private AgentTask? _currentTask;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanCancel))]
    private bool _isCancelling;

    [ObservableProperty]
    private string? _errorMessage;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasFleetNodes))]
    private ObservableCollection<FleetNodeViewModel> _fleetNodes = new();

    [ObservableProperty]
    private FleetNodeViewModel? _selectedFleetNode;

    [ObservableProperty]
    private ObservableCollection<ArtifactModel> _artifacts = new();

    public bool HasCurrentTask => CurrentTask != null;
    public string CurrentTaskId => CurrentTask?.TaskId ?? string.Empty;
    public TaskStatus CurrentTaskStatus => CurrentTask?.Status ?? TaskStatus.SUBMITTED;
    public string CurrentTaskPrompt => CurrentTask?.Prompt ?? string.Empty;
    public RouteSelection? CurrentTaskRouting => CurrentTask?.Routing;
    public System.Collections.Generic.IReadOnlyList<PlanStep> CurrentTaskSteps => (System.Collections.Generic.IReadOnlyList<PlanStep>?)CurrentTask?.Plan?.Steps ?? Array.Empty<PlanStep>();
    public bool CanCancel => CurrentTask != null && !IsCancelling && CurrentTask.Status is not (TaskStatus.COMPLETED or TaskStatus.FAILED or TaskStatus.CANCELLED);
    public bool HasFleetNodes => FleetNodes.Count > 0;

    public event Action<ActionApproval>? ApprovalRequested;

    public TaskDetailViewModel(INexoraApiClient apiClient, ITaskPoller taskPoller)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
        _taskPoller = taskPoller ?? throw new ArgumentNullException(nameof(taskPoller));

        _taskPoller.TaskUpdated += OnTaskUpdated;
        _taskPoller.ApprovalRequired += OnApprovalRequired;
    }

    public void LoadTask(AgentTask task)
    {
        CurrentTask = task;
        if (task.Status is TaskStatus.SUBMITTED or TaskStatus.PARSING or TaskStatus.PLANNING or TaskStatus.EXECUTING)
        {
            _taskPoller.StartPolling(task.TaskId);
        }
    }

    partial void OnCurrentTaskChanged(AgentTask? value)
    {
        FleetNodes.Clear();
        Artifacts.Clear();

        if (value?.FleetPlan?.Nodes != null)
        {
            foreach (var kvp in value.FleetPlan.Nodes)
            {
                var n = kvp.Value;
                FleetNodes.Add(new FleetNodeViewModel
                {
                    NodeId = n.NodeId,
                    Role = n.Role,
                    Objective = n.Objective,
                    State = n.State,
                    Error = n.Error,
                    ResultArtifactId = n.ResultArtifactId,
                });
            }
        }

        if (value?.Artifacts != null)
        {
            foreach (var art in value.Artifacts)
            {
                Artifacts.Add(art);
            }
        }
    }

    private void OnTaskUpdated(AgentTask updatedTask)
    {
        CurrentTask = updatedTask;
    }

    private void OnApprovalRequired(AgentTask task)
    {
        if (task.PendingApproval != null)
        {
            ApprovalRequested?.Invoke(task.PendingApproval);
        }
    }

    [RelayCommand]
    private async Task CancelTaskAsync()
    {
        if (CurrentTask == null || IsCancelling)
        {
            return;
        }

        IsCancelling = true;
        ErrorMessage = null;

        try
        {
            var cancelled = await _apiClient.CancelTaskAsync(CurrentTask.TaskId);
            CurrentTask = cancelled;
            _taskPoller.StopPolling();
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to cancel task: {ex.Message}";
        }
        finally
        {
            IsCancelling = false;
        }
    }
}
