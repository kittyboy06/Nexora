using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class ApprovalDialogViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private ActionApproval? _approval;

    [ObservableProperty]
    private bool _isDeciding;

    [ObservableProperty]
    private string? _errorMessage;

    public event Action<AgentTask>? DecisionCompleted;

    public ApprovalDialogViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    public void SetApproval(ActionApproval approval)
    {
        Approval = approval;
        ErrorMessage = null;
    }

    [RelayCommand]
    private async Task ApproveAsync()
    {
        await DecideAsync(approved: true);
    }

    [RelayCommand]
    private async Task RejectAsync()
    {
        await DecideAsync(approved: false);
    }

    private async Task DecideAsync(bool approved)
    {
        if (Approval == null || IsDeciding)
        {
            return;
        }

        IsDeciding = true;
        ErrorMessage = null;

        try
        {
            var task = await _apiClient.DecideApprovalAsync(Approval.TaskId, Approval.ApprovalId, approved);
            DecisionCompleted?.Invoke(task);
        }
        catch (Exception ex)
        {
            ErrorMessage = $"Failed to register approval decision: {ex.Message}";
        }
        finally
        {
            IsDeciding = false;
        }
    }
}
