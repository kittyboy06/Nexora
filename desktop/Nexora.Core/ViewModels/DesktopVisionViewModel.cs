using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class DesktopVisionViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private bool _isEmergencyStopActive;

    [ObservableProperty]
    private WindowSummaryDto? _selectedWindow;

    [ObservableProperty]
    private TargetWindowBindingDto? _activeBinding;

    [ObservableProperty]
    private UIElementNodeDto? _activeTree;

    [ObservableProperty]
    private ScreenshotEvidenceDto? _latestScreenshot;

    [ObservableProperty]
    private string _searchQuery = string.Empty;

    // Action Execution Form Properties
    [ObservableProperty]
    private string _selectedActionType = "click";

    [ObservableProperty]
    private string _targetElementId = string.Empty;

    [ObservableProperty]
    private int? _relativeCoordX;

    [ObservableProperty]
    private int? _relativeCoordY;

    [ObservableProperty]
    private string _textInput = string.Empty;

    [ObservableProperty]
    private string _expectedPostcondition = string.Empty;

    [ObservableProperty]
    private DesktopActionResultDto? _lastActionResult;

    public ObservableCollection<WindowSummaryDto> Windows { get; } = new();
    public ObservableCollection<ScreenshotEvidenceDto> EvidenceList { get; } = new();
    public ObservableCollection<UIElementNodeDto> FlattenedElements { get; } = new();

    public DesktopVisionViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadWindowsAsync()
    {
        IsLoading = true;
        StatusMessage = "Discovering desktop application windows...";
        try
        {
            var results = await _apiClient.ListDesktopWindowsAsync(
                query: string.IsNullOrWhiteSpace(SearchQuery) ? null : SearchQuery,
                includeShielded: false
            );

            Windows.Clear();
            foreach (var w in results)
            {
                Windows.Add(w);
            }

            ActiveBinding = await _apiClient.GetActiveDesktopBindingAsync();
            StatusMessage = $"Discovered {Windows.Count} desktop windows.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to discover windows: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task BindWindowAsync(WindowSummaryDto? window)
    {
        var target = window ?? SelectedWindow;
        if (target == null)
        {
            StatusMessage = "Please select a window to bind.";
            return;
        }

        IsLoading = true;
        StatusMessage = $"Binding target window HWND {target.Hwnd} ({target.ProcessName})...";
        try
        {
            ActiveBinding = await _apiClient.BindDesktopWindowAsync(target.Hwnd);
            StatusMessage = $"Successfully bound target window: {ActiveBinding.WindowTitle}";

            // Automatically refresh tree and capture frame
            await InspectTreeAsync();
            await CaptureWindowAsync();
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to bind window: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ReleaseBindingAsync()
    {
        IsLoading = true;
        StatusMessage = "Releasing active window binding...";
        try
        {
            await _apiClient.ReleaseDesktopBindingAsync();
            ActiveBinding = null;
            ActiveTree = null;
            FlattenedElements.Clear();
            StatusMessage = "Active window binding released.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to release binding: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task InspectTreeAsync()
    {
        if (ActiveBinding == null)
        {
            StatusMessage = "Cannot inspect tree: No window is currently bound.";
            return;
        }

        IsLoading = true;
        StatusMessage = "Inspecting UI Automation tree...";
        try
        {
            ActiveTree = await _apiClient.InspectDesktopTreeAsync(hwnd: ActiveBinding.Hwnd, maxDepth: 4);

            FlattenedElements.Clear();
            FlattenTreeRecursive(ActiveTree);

            StatusMessage = $"Inspected UI tree with {FlattenedElements.Count} accessible elements.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to inspect UI tree: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task CaptureWindowAsync()
    {
        if (ActiveBinding == null)
        {
            StatusMessage = "Cannot capture: No window is currently bound.";
            return;
        }

        IsLoading = true;
        StatusMessage = "Capturing window-bounded screenshot...";
        try
        {
            LatestScreenshot = await _apiClient.CaptureDesktopWindowAsync(hwnd: ActiveBinding.Hwnd);
            await LoadEvidenceAsync();
            StatusMessage = $"Captured {LatestScreenshot.Width}x{LatestScreenshot.Height} frame (Redacted: {LatestScreenshot.IsRedacted}).";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to capture window: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ExecuteActionAsync()
    {
        if (ActiveBinding == null)
        {
            StatusMessage = "Cannot execute action: No window is currently bound.";
            return;
        }

        if (IsEmergencyStopActive)
        {
            StatusMessage = "Blocked: Emergency stop is actively engaged.";
            return;
        }

        IsLoading = true;
        StatusMessage = $"Executing {SelectedActionType} action with verification...";
        try
        {
            List<int>? coords = null;
            if (RelativeCoordX.HasValue && RelativeCoordY.HasValue)
            {
                coords = new List<int> { RelativeCoordX.Value, RelativeCoordY.Value };
            }

            var req = new DesktopActionRequestDto
            {
                Binding = ActiveBinding,
                ActionType = SelectedActionType,
                TargetElementId = string.IsNullOrWhiteSpace(TargetElementId) ? null : TargetElementId.Trim(),
                RelativeCoords = coords,
                TextInput = string.IsNullOrWhiteSpace(TextInput) ? null : TextInput,
                ExpectedPostcondition = string.IsNullOrWhiteSpace(ExpectedPostcondition) ? null : ExpectedPostcondition.Trim(),
            };

            LastActionResult = await _apiClient.ExecuteDesktopActionAsync(req);

            // Refresh tree and evidence after action
            await InspectTreeAsync();
            await LoadEvidenceAsync();

            StatusMessage = $"Action {LastActionResult.Status}: {LastActionResult.Message}";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Action execution failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task TriggerEmergencyStopAsync(string? reason)
    {
        var msg = reason ?? "Operator emergency stop triggered from UI";
        IsLoading = true;
        StatusMessage = "ENGAGING EMERGENCY STOP...";
        try
        {
            await _apiClient.TriggerEmergencyStopAsync(reason: msg);
            IsEmergencyStopActive = true;
            StatusMessage = "EMERGENCY STOP ACTIVE: All desktop automation halted.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to trigger emergency stop: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ResetEmergencyStopAsync()
    {
        IsLoading = true;
        StatusMessage = "Resetting emergency stop state...";
        try
        {
            await _apiClient.ResetEmergencyStopAsync();
            IsEmergencyStopActive = false;
            StatusMessage = "Emergency stop reset. Automation can resume.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to reset emergency stop: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task LoadEvidenceAsync()
    {
        try
        {
            var evidence = await _apiClient.ListDesktopEvidenceAsync();
            EvidenceList.Clear();
            foreach (var e in evidence)
            {
                EvidenceList.Add(e);
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load evidence: {ex.Message}";
        }
    }

    private void FlattenTreeRecursive(UIElementNodeDto node)
    {
        FlattenedElements.Add(node);
        foreach (var child in node.Children)
        {
            FlattenTreeRecursive(child);
        }
    }
}
