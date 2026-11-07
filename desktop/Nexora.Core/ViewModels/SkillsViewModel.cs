using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;

namespace Nexora.Desktop.ViewModels;

public partial class SkillsViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private bool _isLoadingInstalled;

    [ObservableProperty]
    private bool _isSearchingGitHub;

    [ObservableProperty]
    private string _searchQuery = string.Empty;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private SkillSummaryDto? _selectedSkill;

    [ObservableProperty]
    private SkillBundleDto? _inspectedBundle;

    [ObservableProperty]
    private SkillDiscoveryCandidateDto? _selectedCandidate;

    [ObservableProperty]
    private GitHubRateLimitStatusDto? _rateLimitStatus;

    [ObservableProperty]
    private string? _markdownPreview;

    public ObservableCollection<SkillSummaryDto> InstalledSkills { get; } = new();
    public ObservableCollection<SkillDiscoveryCandidateDto> DiscoveryCandidates { get; } = new();

    public SkillsViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadInstalledSkillsAsync()
    {
        IsLoadingInstalled = true;
        StatusMessage = "Loading installed skills...";
        try
        {
            var skills = await _apiClient.ListSkillsAsync();
            InstalledSkills.Clear();
            foreach (var s in skills)
            {
                InstalledSkills.Add(s);
            }
            StatusMessage = $"Loaded {skills.Count} installed skills.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load skills: {ex.Message}";
        }
        finally
        {
            IsLoadingInstalled = false;
        }
    }

    [RelayCommand]
    public async Task ToggleSkillAsync(SkillSummaryDto? skill)
    {
        if (skill == null) return;
        try
        {
            var updated = await _apiClient.PatchSkillAsync(skill.Id, isEnabled: !skill.IsEnabled);
            skill.IsEnabled = updated.IsEnabled;
            StatusMessage = $"Skill '{skill.Id}' is now {(skill.IsEnabled ? "Enabled" : "Disabled")}.";
            await LoadInstalledSkillsAsync();
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to toggle skill: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task InspectSkillAsync(SkillSummaryDto? skill)
    {
        if (skill == null) return;
        try
        {
            SelectedSkill = skill;
            var bundle = await _apiClient.GetSkillAsync(skill.Id);
            InspectedBundle = bundle;
            MarkdownPreview = bundle.Instructions;
            StatusMessage = $"Viewing guidance for '{skill.Name}' v{skill.Version}.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to inspect skill: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task DeleteSkillAsync(SkillSummaryDto? skill)
    {
        if (skill == null) return;
        try
        {
            await _apiClient.DeleteSkillAsync(skill.Id);
            StatusMessage = $"Deleted skill '{skill.Id}'.";
            if (SelectedSkill?.Id == skill.Id)
            {
                SelectedSkill = null;
                InspectedBundle = null;
                MarkdownPreview = null;
            }
            await LoadInstalledSkillsAsync();
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to delete skill: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task SearchGitHubAsync()
    {
        IsSearchingGitHub = true;
        StatusMessage = "Searching GitHub for skills...";
        try
        {
            var candidates = await _apiClient.SearchDiscoveryAsync(SearchQuery);
            DiscoveryCandidates.Clear();
            foreach (var c in candidates)
            {
                DiscoveryCandidates.Add(c);
            }
            await RefreshRateLimitAsync();
            StatusMessage = $"Found {candidates.Count} repository candidates.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"GitHub search error: {ex.Message}";
        }
        finally
        {
            IsSearchingGitHub = false;
        }
    }

    [RelayCommand]
    public async Task PreviewCandidateAsync(SkillDiscoveryCandidateDto? candidate)
    {
        if (candidate == null) return;
        try
        {
            SelectedCandidate = candidate;
            StatusMessage = $"Fetching preview from {candidate.Owner}/{candidate.Repo}...";
            var preview = await _apiClient.PreviewDiscoveryAsync(candidate.Owner, candidate.Repo, candidate.DefaultBranch);
            SelectedCandidate = preview;
            MarkdownPreview = preview.SkillMdPreview ?? "(No SKILL.md found in this repository)";
            StatusMessage = preview.HasManifest && preview.HasSkillMd
                ? "Repository verified. Ready to install."
                : "Notice: Repository is missing manifest.json or SKILL.md.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Preview error: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task InstallCandidateAsync(SkillDiscoveryCandidateDto? candidate)
    {
        if (candidate == null) return;
        try
        {
            StatusMessage = $"Installing skill from {candidate.Owner}/{candidate.Repo}...";
            var request = new InstallSkillRequestDto
            {
                Owner = candidate.Owner,
                Repo = candidate.Repo,
                Branch = candidate.DefaultBranch,
            };
            var installed = await _apiClient.InstallSkillAsync(request);
            StatusMessage = $"Successfully installed '{installed.Manifest.Name}' v{installed.Manifest.Version}!";
            await LoadInstalledSkillsAsync();
        }
        catch (Exception ex)
        {
            StatusMessage = $"Installation failed: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task RefreshRateLimitAsync()
    {
        try
        {
            RateLimitStatus = await _apiClient.GetGitHubRateLimitAsync();
        }
        catch
        {
            // Ignore rate limit status failure
        }
    }
}
