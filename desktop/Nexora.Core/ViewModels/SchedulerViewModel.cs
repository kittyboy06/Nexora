using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class SchedulerViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private string _errorMessage = string.Empty;

    [ObservableProperty]
    private ScheduleDto? _selectedSchedule;

    [ObservableProperty]
    private string? _filterStatus;

    // Creation / Edit Form State
    [ObservableProperty]
    private string _formName = string.Empty;

    [ObservableProperty]
    private string _formPromptTemplate = string.Empty;

    [ObservableProperty]
    private string? _formModelProfileId;

    [ObservableProperty]
    private TriggerType _formTriggerType = TriggerType.INTERVAL;

    [ObservableProperty]
    private string _formTriggerExpression = "30m";

    [ObservableProperty]
    private string _formTimezone = "UTC";

    [ObservableProperty]
    private MissedRunPolicy _formMissedRunPolicy = MissedRunPolicy.SKIP_NOTIFY;

    [ObservableProperty]
    private ConcurrencyPolicy _formConcurrencyPolicy = ConcurrencyPolicy.SKIP_BUSY;

    [ObservableProperty]
    private int _formRetryGraceSeconds = 300;

    [ObservableProperty]
    private bool _isCreateDialogOpen;

    public ObservableCollection<ScheduleDto> Schedules { get; } = new();
    public ObservableCollection<ScheduleRunDto> ScheduleRuns { get; } = new();

    public SchedulerViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadSchedulesAsync()
    {
        IsLoading = true;
        ErrorMessage = string.Empty;
        try
        {
            var schedules = await _apiClient.ListSchedulesAsync(FilterStatus);
            Schedules.Clear();
            foreach (var item in schedules)
            {
                Schedules.Add(item);
            }

            await LoadRecentRunsAsync();
            StatusMessage = $"Loaded {Schedules.Count} schedules.";
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to load schedules: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task LoadRecentRunsAsync()
    {
        try
        {
            var scheduleId = SelectedSchedule?.Id;
            var runs = await _apiClient.ListScheduleRunsAsync(scheduleId: scheduleId, limit: 30);
            ScheduleRuns.Clear();
            foreach (var run in runs)
            {
                ScheduleRuns.Add(run);
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to load runs: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task CreateScheduleAsync()
    {
        if (string.IsNullOrWhiteSpace(FormName) || string.IsNullOrWhiteSpace(FormPromptTemplate) || string.IsNullOrWhiteSpace(FormTriggerExpression))
        {
            ErrorMessage = "Name, Prompt, and Trigger Expression are required.";
            return;
        }

        IsLoading = true;
        ErrorMessage = string.Empty;
        try
        {
            var req = new ScheduleCreateRequest
            {
                Name = FormName.Trim(),
                PromptTemplate = FormPromptTemplate.Trim(),
                ModelProfileId = string.IsNullOrWhiteSpace(FormModelProfileId) ? null : FormModelProfileId.Trim(),
                TriggerType = FormTriggerType,
                TriggerExpression = FormTriggerExpression.Trim(),
                Timezone = string.IsNullOrWhiteSpace(FormTimezone) ? "UTC" : FormTimezone.Trim(),
                MissedRunPolicy = FormMissedRunPolicy,
                ConcurrencyPolicy = FormConcurrencyPolicy,
                MaxInstances = 1,
                RetryGraceSeconds = FormRetryGraceSeconds
            };

            var created = await _apiClient.CreateScheduleAsync(req);
            Schedules.Insert(0, created);
            SelectedSchedule = created;
            IsCreateDialogOpen = false;
            ResetForm();
            StatusMessage = $"Schedule '{created.Name}' created successfully.";
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to create schedule: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task TogglePauseAsync(ScheduleDto? schedule)
    {
        var target = schedule ?? SelectedSchedule;
        if (target == null) return;

        IsLoading = true;
        ErrorMessage = string.Empty;
        try
        {
            ScheduleDto updated;
            if (target.Status == ScheduleStatus.ACTIVE)
            {
                updated = await _apiClient.PauseScheduleAsync(target.Id);
                StatusMessage = $"Schedule '{target.Name}' paused.";
            }
            else
            {
                updated = await _apiClient.ResumeScheduleAsync(target.Id);
                StatusMessage = $"Schedule '{target.Name}' resumed and active.";
            }

            var idx = Schedules.IndexOf(target);
            if (idx >= 0)
            {
                Schedules[idx] = updated;
            }
            if (SelectedSchedule?.Id == target.Id)
            {
                SelectedSchedule = updated;
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to update schedule status: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task RunNowAsync(ScheduleDto? schedule)
    {
        var target = schedule ?? SelectedSchedule;
        if (target == null) return;

        IsLoading = true;
        ErrorMessage = string.Empty;
        try
        {
            var run = await _apiClient.TriggerScheduleAsync(target.Id);
            ScheduleRuns.Insert(0, run);
            StatusMessage = $"Triggered immediate run for '{target.Name}' (Run ID: {run.RunId}).";
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to trigger run: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task DeleteScheduleAsync(ScheduleDto? schedule)
    {
        var target = schedule ?? SelectedSchedule;
        if (target == null) return;

        IsLoading = true;
        ErrorMessage = string.Empty;
        try
        {
            var deleted = await _apiClient.DeleteScheduleAsync(target.Id);
            if (deleted)
            {
                Schedules.Remove(target);
                if (SelectedSchedule?.Id == target.Id)
                {
                    SelectedSchedule = null;
                }
                await LoadRecentRunsAsync();
                StatusMessage = $"Schedule '{target.Name}' deleted.";
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to delete schedule: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    public void ResetForm()
    {
        FormName = string.Empty;
        FormPromptTemplate = string.Empty;
        FormModelProfileId = null;
        FormTriggerType = TriggerType.INTERVAL;
        FormTriggerExpression = "30m";
        FormTimezone = "UTC";
        FormMissedRunPolicy = MissedRunPolicy.SKIP_NOTIFY;
        FormConcurrencyPolicy = ConcurrencyPolicy.SKIP_BUSY;
        FormRetryGraceSeconds = 300;
    }
}
