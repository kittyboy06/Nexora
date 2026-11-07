using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class TaskComposerViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanSubmit))]
    private string _prompt = string.Empty;

    [ObservableProperty]
    private string? _selectedProfileId;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanSubmit))]
    private bool _isSubmitting;

    [ObservableProperty]
    private string? _errorMessage;

    public bool CanSubmit => !string.IsNullOrWhiteSpace(Prompt) && !IsSubmitting;

    public ObservableCollection<ModelProfileStatus> AvailableProfiles { get; } = new();

    public event Action<AgentTask>? TaskCreated;

    public TaskComposerViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    public async Task LoadProfilesAsync()
    {
        try
        {
            var response = await _apiClient.GetModelProfilesAsync();
            AvailableProfiles.Clear();
            foreach (var profile in response.Profiles)
            {
                if (profile.Enabled && profile.Installed && profile.Role != "router")
                {
                    AvailableProfiles.Add(profile);
                }
            }
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to load model profiles: {ex.Message}";
        }
    }

    [RelayCommand]
    private async Task SubmitTaskAsync()
    {
        if (string.IsNullOrWhiteSpace(Prompt) || IsSubmitting)
        {
            return;
        }

        IsSubmitting = true;
        ErrorMessage = null;

        try
        {
            var task = await _apiClient.CreateTaskAsync(Prompt.Trim(), SelectedProfileId);
            Prompt = string.Empty;
            TaskCreated?.Invoke(task);
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Task submission failed: {ex.Message}";
        }
        finally
        {
            IsSubmitting = false;
        }
    }
}
