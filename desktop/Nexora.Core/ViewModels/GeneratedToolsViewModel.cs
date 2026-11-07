using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class GeneratedToolsViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private GeneratedToolRecordDto? _selectedTool;

    [ObservableProperty]
    private SandboxRunResultDto? _selectedEvidence;

    [ObservableProperty]
    private ToolValidationReportDto? _latestValidationReport;

    [ObservableProperty]
    private SandboxRunResultDto? _latestTrialResult;

    // Proposal Form Fields
    [ObservableProperty]
    private string _proposalName = string.Empty;

    [ObservableProperty]
    private string _proposalDescription = string.Empty;

    [ObservableProperty]
    private string _proposalCode = string.Empty;

    [ObservableProperty]
    private string _proposalTestInputs = "{}";

    [ObservableProperty]
    private string _proposalExpectedOutput = string.Empty;

    public ObservableCollection<GeneratedToolRecordDto> Tools { get; } = new();
    public ObservableCollection<SandboxRunResultDto> EvidenceRuns { get; } = new();
    public ObservableCollection<string> ToolVersions { get; } = new();

    public GeneratedToolsViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadAllAsync()
    {
        IsLoading = true;
        StatusMessage = "Loading generated tools and sandbox evidence...";
        try
        {
            var tools = await _apiClient.ListGeneratedToolsAsync();
            Tools.Clear();
            foreach (var t in tools)
            {
                Tools.Add(t);
            }

            var evidence = await _apiClient.ListSandboxEvidenceAsync(50);
            EvidenceRuns.Clear();
            foreach (var ev in evidence)
            {
                EvidenceRuns.Add(ev);
            }

            StatusMessage = $"Loaded {Tools.Count} tools, {EvidenceRuns.Count} evidence records.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load data: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task SelectToolAsync(GeneratedToolRecordDto? tool)
    {
        SelectedTool = tool;
        ToolVersions.Clear();
        if (tool == null) return;

        try
        {
            var versions = await _apiClient.ListGeneratedToolVersionsAsync(tool.Manifest.Name);
            foreach (var v in versions)
            {
                ToolVersions.Add(v);
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load versions: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task ValidateProposalAsync()
    {
        if (string.IsNullOrWhiteSpace(ProposalName) || string.IsNullOrWhiteSpace(ProposalCode))
        {
            StatusMessage = "Tool Name and Code are required.";
            return;
        }

        IsLoading = true;
        StatusMessage = "Validating proposal statically via AST...";
        try
        {
            var proposal = BuildCurrentProposal();
            LatestValidationReport = await _apiClient.ValidateToolProposalAsync(proposal);
            if (LatestValidationReport != null && LatestValidationReport.IsValid)
            {
                StatusMessage = "AST Security Validation Passed cleanly.";
            }
            else
            {
                var errors = LatestValidationReport?.Errors != null ? string.Join(", ", LatestValidationReport.Errors) : "Validation failed";
                StatusMessage = $"Validation Errors: {errors}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Validation request failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task RunTrialAsync()
    {
        if (string.IsNullOrWhiteSpace(ProposalName) || string.IsNullOrWhiteSpace(ProposalCode))
        {
            StatusMessage = "Tool Name and Code are required.";
            return;
        }

        IsLoading = true;
        StatusMessage = "Executing trial in isolated Windows Job Object sandbox...";
        try
        {
            var proposal = BuildCurrentProposal();
            var trialReq = new TrialRunRequestDto
            {
                Proposal = proposal,
                Mode = "test",
            };

            LatestTrialResult = await _apiClient.RunSandboxTrialAsync(trialReq);
            if (LatestTrialResult != null)
            {
                StatusMessage = $"Trial Complete: {LatestTrialResult.Status} in {LatestTrialResult.ExecutionTimeMs}ms (Peak RAM: {LatestTrialResult.PeakMemoryBytes / 1024 / 1024}MB)";
                // Refresh evidence
                var evidence = await _apiClient.ListSandboxEvidenceAsync(50);
                EvidenceRuns.Clear();
                foreach (var ev in evidence)
                {
                    EvidenceRuns.Add(ev);
                }
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Sandbox trial execution failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task PromoteProposalAsync()
    {
        if (LatestTrialResult == null)
        {
            StatusMessage = "Cannot promote: No successful trial run evidence available.";
            return;
        }

        if (LatestTrialResult.Status != "TESTS_PASSED")
        {
            StatusMessage = $"Cannot promote: Trial status is '{LatestTrialResult.Status}', must be 'TESTS_PASSED'.";
            return;
        }

        IsLoading = true;
        StatusMessage = "Promoting generated tool to catalog...";
        try
        {
            var proposal = BuildCurrentProposal();
            var promoteReq = new ToolPromotionRequestDto
            {
                Proposal = proposal,
                EvidenceRunId = LatestTrialResult.RunId,
                Reviewer = "operator",
            };

            var promoted = await _apiClient.PromoteToolAsync(promoteReq);
            if (promoted != null)
            {
                await LoadAllAsync();
                SelectedTool = Tools.FirstOrDefault(t => t.Manifest.Name == promoted.Manifest.Name);
                StatusMessage = $"Successfully promoted '{promoted.Manifest.Name}' v{promoted.Manifest.Version} to catalog.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Promotion failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ToggleToolEnabledAsync(GeneratedToolRecordDto? tool)
    {
        var target = tool ?? SelectedTool;
        if (target == null) return;

        IsLoading = true;
        var newState = !target.IsEnabled;
        StatusMessage = $"Updating tool {target.Manifest.Name} enabled state to {newState}...";
        try
        {
            var updated = await _apiClient.UpdateGeneratedToolAsync(target.Manifest.Name, new ToolUpdateRequestDto { IsEnabled = newState });
            if (updated != null)
            {
                target.IsEnabled = updated.IsEnabled;
                StatusMessage = $"Tool {target.Manifest.Name} is now {(updated.IsEnabled ? "Enabled" : "Disabled")}.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to update tool: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task RollbackToolVersionAsync(string? targetVersion)
    {
        if (SelectedTool == null || string.IsNullOrWhiteSpace(targetVersion)) return;

        IsLoading = true;
        StatusMessage = $"Rolling back {SelectedTool.Manifest.Name} to version {targetVersion}...";
        try
        {
            var updated = await _apiClient.UpdateGeneratedToolAsync(SelectedTool.Manifest.Name, new ToolUpdateRequestDto { TargetVersion = targetVersion });
            if (updated != null)
            {
                await LoadAllAsync();
                SelectedTool = updated;
                StatusMessage = $"Rolled back {updated.Manifest.Name} to v{updated.Manifest.Version}.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Rollback failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task DeleteToolAsync(GeneratedToolRecordDto? tool)
    {
        var target = tool ?? SelectedTool;
        if (target == null) return;

        IsLoading = true;
        StatusMessage = $"Deleting generated tool {target.Manifest.Name}...";
        try
        {
            var deleted = await _apiClient.DeleteGeneratedToolAsync(target.Manifest.Name);
            if (deleted)
            {
                SelectedTool = null;
                await LoadAllAsync();
                StatusMessage = $"Deleted tool {target.Manifest.Name}.";
            }
            else
            {
                StatusMessage = $"Failed to delete tool {target.Manifest.Name}.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Delete request failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    private GeneratedToolProposalDto BuildCurrentProposal()
    {
        Dictionary<string, object?> parsedInputs = new();
        try
        {
            if (!string.IsNullOrWhiteSpace(ProposalTestInputs))
            {
                parsedInputs = JsonSerializer.Deserialize<Dictionary<string, object?>>(ProposalTestInputs) ?? new();
            }
        }
        catch
        {
            // fallback
        }

        return new GeneratedToolProposalDto
        {
            Name = ProposalName.Trim(),
            Description = ProposalDescription.Trim(),
            Code = ProposalCode,
            InputSchema = new Dictionary<string, object?> { ["type"] = "object" },
            OutputSchema = new Dictionary<string, object?> { ["type"] = "object" },
            TestCases = new List<TestCaseDto>
            {
                new TestCaseDto
                {
                    Name = "pos_verification",
                    Inputs = parsedInputs,
                    ExpectedOutput = string.IsNullOrWhiteSpace(ProposalExpectedOutput) ? null : ProposalExpectedOutput,
                    IsNegative = false,
                },
                new TestCaseDto
                {
                    Name = "neg_verification",
                    Inputs = new Dictionary<string, object?>(),
                    ExpectedOutput = null,
                    IsNegative = true,
                },
            },
        };
    }
}
