using CommunityToolkit.Mvvm.ComponentModel;
using Nexora.Desktop.Models;

namespace Nexora.Desktop.ViewModels;

public partial class FleetNodeViewModel : ObservableObject
{
    [ObservableProperty]
    private string _nodeId = string.Empty;

    [ObservableProperty]
    private string _role = string.Empty;

    [ObservableProperty]
    private string _objective = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(StatusBadgeText))]
    [NotifyPropertyChangedFor(nameof(StatusColor))]
    [NotifyPropertyChangedFor(nameof(IsCompleted))]
    [NotifyPropertyChangedFor(nameof(IsRunning))]
    [NotifyPropertyChangedFor(nameof(IsBlocked))]
    private FleetNodeState _state = FleetNodeState.QUEUED;

    [ObservableProperty]
    private string? _error;

    [ObservableProperty]
    private string? _resultArtifactId;

    [ObservableProperty]
    private bool _isSelected;

    public string StatusBadgeText => State switch
    {
        FleetNodeState.COMPLETED => "✓ Done",
        FleetNodeState.RUNNING => "● Running",
        FleetNodeState.WAITING_APPROVAL => "⏸ Approval",
        FleetNodeState.BLOCKED => "⊘ Blocked",
        FleetNodeState.FAILED => "✕ Failed",
        FleetNodeState.CANCELLED => "— Cancelled",
        FleetNodeState.READY => "Ready",
        _ => "Queued"
    };

    public string StatusColor => State switch
    {
        FleetNodeState.COMPLETED => "#107C41",         // Forest Green
        FleetNodeState.RUNNING => "#0078D4",           // Accent Blue
        FleetNodeState.WAITING_APPROVAL => "#CA5010",  // Amber
        FleetNodeState.BLOCKED => "#A80000",          // Dark Red
        FleetNodeState.FAILED => "#D13438",           // Crimson
        FleetNodeState.READY => "#004E8C",            // Deep Blue
        _ => "#605E5C"                                 // Neutral Gray
    };

    public bool IsCompleted => State == FleetNodeState.COMPLETED;
    public bool IsRunning => State == FleetNodeState.RUNNING;
    public bool IsBlocked => State == FleetNodeState.BLOCKED;
}
