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

public partial class MemoryViewModel : ObservableObject
{
    private readonly INexoraApiClient _apiClient;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    [ObservableProperty]
    private MemoryRecordDto? _selectedRecord;

    [ObservableProperty]
    private string _searchQuery = string.Empty;

    [ObservableProperty]
    private string? _selectedCategoryFilter;

    [ObservableProperty]
    private string? _selectedStatusFilter;

    // Creation Form Properties
    [ObservableProperty]
    private string _newKey = string.Empty;

    [ObservableProperty]
    private string _newCategory = "user_preference";

    [ObservableProperty]
    private string _newValue = string.Empty;

    [ObservableProperty]
    private string _newSensitivity = "LOW";

    [ObservableProperty]
    private string _newReason = string.Empty;

    [ObservableProperty]
    private int? _newTtlDays;

    [ObservableProperty]
    private string _exportResult = string.Empty;

    public ObservableCollection<MemoryRecordDto> Memories { get; } = new();
    public ObservableCollection<MemoryAuditEntryDto> AuditEntries { get; } = new();
    public ObservableCollection<MemoryBackupInfoDto> Backups { get; } = new();

    public MemoryViewModel(INexoraApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
    }

    [RelayCommand]
    public async Task LoadAllAsync()
    {
        IsLoading = true;
        StatusMessage = "Loading memories, audit trail, and backups...";
        try
        {
            var records = await _apiClient.ListMemoriesAsync(
                category: SelectedCategoryFilter,
                status: SelectedStatusFilter,
                query: string.IsNullOrWhiteSpace(SearchQuery) ? null : SearchQuery,
                limit: 100);

            Memories.Clear();
            foreach (var r in records)
            {
                Memories.Add(r);
            }

            var audits = await _apiClient.ListMemoryAuditAsync(limit: 50);
            AuditEntries.Clear();
            foreach (var a in audits)
            {
                AuditEntries.Add(a);
            }

            var backups = await _apiClient.ListMemoryBackupsAsync();
            Backups.Clear();
            foreach (var b in backups)
            {
                Backups.Add(b);
            }

            StatusMessage = $"Loaded {Memories.Count} memories, {AuditEntries.Count} audit entries.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load memories: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task SearchMemoriesAsync()
    {
        await LoadAllAsync();
    }

    [RelayCommand]
    public async Task SelectRecordAsync(MemoryRecordDto? record)
    {
        SelectedRecord = record;
        if (record == null) return;

        try
        {
            var audits = await _apiClient.ListMemoryAuditAsync(memoryId: record.Id, limit: 20);
            AuditEntries.Clear();
            foreach (var a in audits)
            {
                AuditEntries.Add(a);
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to load record audit: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task CreateMemoryAsync()
    {
        if (string.IsNullOrWhiteSpace(NewKey) || string.IsNullOrWhiteSpace(NewValue))
        {
            StatusMessage = "Key and Value are required.";
            return;
        }

        IsLoading = true;
        StatusMessage = "Creating memory record...";
        try
        {
            var proposal = new MemoryProposalDto
            {
                Key = NewKey.Trim(),
                Category = NewCategory,
                Value = NewValue.Trim(),
                Sensitivity = NewSensitivity,
                ProvenanceReason = string.IsNullOrWhiteSpace(NewReason) ? "Manual operator entry" : NewReason.Trim(),
                TtlDays = NewTtlDays,
            };

            var created = await _apiClient.CreateMemoryAsync(proposal, autoApprove: true);
            if (created != null)
            {
                await LoadAllAsync();
                SelectedRecord = Memories.FirstOrDefault(m => m.Id == created.Id);
                StatusMessage = $"Successfully created memory '{created.Key}' ({created.Status}).";
                NewKey = string.Empty;
                NewValue = string.Empty;
                NewReason = string.Empty;
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to create memory: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ApproveMemoryAsync(MemoryRecordDto? record)
    {
        var target = record ?? SelectedRecord;
        if (target == null) return;

        IsLoading = true;
        StatusMessage = $"Approving memory {target.Key}...";
        try
        {
            var approved = await _apiClient.ApproveMemoryAsync(target.Id);
            if (approved != null)
            {
                target.Status = approved.Status;
                await LoadAllAsync();
                StatusMessage = $"Approved memory {approved.Key}.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to approve memory: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task RevokeMemoryAsync(MemoryRecordDto? record)
    {
        var target = record ?? SelectedRecord;
        if (target == null) return;

        IsLoading = true;
        StatusMessage = $"Revoking memory {target.Key}...";
        try
        {
            var revoked = await _apiClient.RevokeMemoryAsync(target.Id);
            if (revoked)
            {
                await LoadAllAsync();
                StatusMessage = $"Revoked memory {target.Key}.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to revoke memory: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task DeleteMemoryAsync(MemoryRecordDto? record)
    {
        var target = record ?? SelectedRecord;
        if (target == null) return;

        IsLoading = true;
        StatusMessage = $"Permanently deleting memory {target.Key}...";
        try
        {
            var deleted = await _apiClient.DeleteMemoryAsync(target.Id);
            if (deleted)
            {
                SelectedRecord = null;
                await LoadAllAsync();
                StatusMessage = $"Permanently deleted memory {target.Key}.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Failed to delete memory: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task CreateBackupAsync()
    {
        IsLoading = true;
        StatusMessage = "Creating online SQLite backup...";
        try
        {
            var backup = await _apiClient.CreateMemoryBackupAsync();
            if (backup != null)
            {
                await LoadAllAsync();
                StatusMessage = $"Created backup with {backup.RecordCount} records ({backup.FileSizeBytes} bytes).";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Backup failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task RestoreBackupAsync(string? backupPath)
    {
        if (string.IsNullOrWhiteSpace(backupPath)) return;

        IsLoading = true;
        StatusMessage = $"Restoring database from {backupPath}...";
        try
        {
            var restored = await _apiClient.RestoreMemoryBackupAsync(backupPath);
            if (restored)
            {
                await LoadAllAsync();
                StatusMessage = "Database successfully restored from backup.";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Restore failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task ExportMemoriesAsync(string? format)
    {
        var fmt = string.IsNullOrWhiteSpace(format) ? "json" : format.ToLowerInvariant();
        IsLoading = true;
        StatusMessage = $"Exporting memories as {fmt.ToUpperInvariant()}...";
        try
        {
            ExportResult = await _apiClient.ExportMemoriesAsync(format: fmt);
            StatusMessage = $"Export complete ({ExportResult.Length} characters).";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Export failed: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }
}
