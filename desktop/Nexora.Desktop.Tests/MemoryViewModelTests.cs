using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class MemoryViewModelTests
{
    [Fact]
    public async Task LoadAllAsync_PopulatesMemoriesAuditAndBackups()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var records = new List<MemoryRecordDto>
        {
            new()
            {
                Id = "mem_001",
                Key = "user_preference:theme",
                Category = "user_preference",
                Value = "dark",
                Sensitivity = "LOW",
                Status = "ACTIVE",
            },
        };
        var audits = new List<MemoryAuditEntryDto>
        {
            new()
            {
                Id = 1,
                Action = "CREATE",
                Actor = "user",
                MemoryId = "mem_001",
                Timestamp = "2026-11-07T12:00:00Z",
            },
        };
        var backups = new List<MemoryBackupInfoDto>
        {
            new()
            {
                BackupPath = "backups/mem_backup_1.db",
                FileSizeBytes = 40960,
                RecordCount = 1,
                CreatedAt = "2026-11-07T12:05:00Z",
                IsValid = true,
            },
        };

        mockClient
            .Setup(c => c.ListMemoriesAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), 100, It.IsAny<CancellationToken>()))
            .ReturnsAsync(records);
        mockClient
            .Setup(c => c.ListMemoryAuditAsync(It.IsAny<string?>(), 50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(audits);
        mockClient
            .Setup(c => c.ListMemoryBackupsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(backups);

        var vm = new MemoryViewModel(mockClient.Object);
        await vm.LoadAllCommand.ExecuteAsync(null);

        Assert.Single(vm.Memories);
        Assert.Equal("user_preference:theme", vm.Memories[0].Key);
        Assert.Single(vm.AuditEntries);
        Assert.Equal(1, vm.AuditEntries[0].Id);
        Assert.Single(vm.Backups);
        Assert.Equal("backups/mem_backup_1.db", vm.Backups[0].BackupPath);
        Assert.Contains("Loaded 1 memories", vm.StatusMessage);
    }

    [Fact]
    public async Task CreateMemoryAsync_ValidationFails_WhenKeyOrValueEmpty()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var vm = new MemoryViewModel(mockClient.Object)
        {
            NewKey = "",
            NewValue = "",
        };

        await vm.CreateMemoryCommand.ExecuteAsync(null);

        Assert.Equal("Key and Value are required.", vm.StatusMessage);
        mockClient.Verify(c => c.CreateMemoryAsync(It.IsAny<MemoryProposalDto>(), It.IsAny<bool>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task CreateMemoryAsync_Success_ResetsFieldsAndReloads()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var created = new MemoryRecordDto
        {
            Id = "mem_002",
            Key = "pref:editor",
            Category = "user_preference",
            Value = "vscode",
            Sensitivity = "LOW",
            Status = "ACTIVE",
        };

        mockClient
            .Setup(c => c.CreateMemoryAsync(It.IsAny<MemoryProposalDto>(), true, It.IsAny<CancellationToken>()))
            .ReturnsAsync(created);
        mockClient
            .Setup(c => c.ListMemoriesAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), 100, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryRecordDto> { created });
        mockClient
            .Setup(c => c.ListMemoryAuditAsync(It.IsAny<string?>(), 50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryAuditEntryDto>());
        mockClient
            .Setup(c => c.ListMemoryBackupsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryBackupInfoDto>());

        var vm = new MemoryViewModel(mockClient.Object)
        {
            NewKey = "pref:editor",
            NewValue = "vscode",
            NewCategory = "user_preference",
            NewSensitivity = "LOW",
            NewReason = "Operator favorite",
        };

        await vm.CreateMemoryCommand.ExecuteAsync(null);

        Assert.Empty(vm.NewKey);
        Assert.Empty(vm.NewValue);
        Assert.Empty(vm.NewReason);
        Assert.Contains("Successfully created memory 'pref:editor'", vm.StatusMessage);
        Assert.Single(vm.Memories);
        Assert.NotNull(vm.SelectedRecord);
        Assert.Equal("mem_002", vm.SelectedRecord.Id);
    }

    [Fact]
    public async Task ApproveMemoryAsync_CallsApiAndUpdatesStatus()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var record = new MemoryRecordDto
        {
            Id = "mem_003",
            Key = "project:db_schema",
            Category = "project_fact",
            Value = "PostgreSQL 16",
            Sensitivity = "MEDIUM",
            Status = "PENDING_APPROVAL",
        };
        var approved = new MemoryRecordDto
        {
            Id = "mem_003",
            Key = "project:db_schema",
            Category = "project_fact",
            Value = "PostgreSQL 16",
            Sensitivity = "MEDIUM",
            Status = "ACTIVE",
        };

        mockClient
            .Setup(c => c.ApproveMemoryAsync("mem_003", It.IsAny<CancellationToken>()))
            .ReturnsAsync(approved);
        mockClient
            .Setup(c => c.ListMemoriesAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), 100, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryRecordDto> { approved });
        mockClient
            .Setup(c => c.ListMemoryAuditAsync(It.IsAny<string?>(), 50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryAuditEntryDto>());
        mockClient
            .Setup(c => c.ListMemoryBackupsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryBackupInfoDto>());

        var vm = new MemoryViewModel(mockClient.Object);
        await vm.ApproveMemoryCommand.ExecuteAsync(record);

        Assert.Equal("ACTIVE", record.Status);
        Assert.Contains("Approved memory project:db_schema", vm.StatusMessage);
        mockClient.Verify(c => c.ApproveMemoryAsync("mem_003", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task RevokeMemoryAsync_CallsApiAndReloads()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var record = new MemoryRecordDto
        {
            Id = "mem_004",
            Key = "rule:no_force_push",
            Status = "ACTIVE",
        };

        mockClient
            .Setup(c => c.RevokeMemoryAsync("mem_004", It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        mockClient
            .Setup(c => c.ListMemoriesAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), 100, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryRecordDto>());
        mockClient
            .Setup(c => c.ListMemoryAuditAsync(It.IsAny<string?>(), 50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryAuditEntryDto>());
        mockClient
            .Setup(c => c.ListMemoryBackupsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryBackupInfoDto>());

        var vm = new MemoryViewModel(mockClient.Object);
        await vm.RevokeMemoryCommand.ExecuteAsync(record);

        Assert.Contains("Revoked memory rule:no_force_push", vm.StatusMessage);
        mockClient.Verify(c => c.RevokeMemoryAsync("mem_004", It.IsAny<string>(), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task DeleteMemoryAsync_CallsApiAndClearsSelection()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var record = new MemoryRecordDto
        {
            Id = "mem_005",
            Key = "temp:scratch",
            Status = "REVOKED",
        };

        mockClient
            .Setup(c => c.DeleteMemoryAsync("mem_005", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        mockClient
            .Setup(c => c.ListMemoriesAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), 100, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryRecordDto>());
        mockClient
            .Setup(c => c.ListMemoryAuditAsync(It.IsAny<string?>(), 50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryAuditEntryDto>());
        mockClient
            .Setup(c => c.ListMemoryBackupsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryBackupInfoDto>());

        var vm = new MemoryViewModel(mockClient.Object)
        {
            SelectedRecord = record,
        };

        await vm.DeleteMemoryCommand.ExecuteAsync(record);

        Assert.Null(vm.SelectedRecord);
        Assert.Contains("Permanently deleted memory temp:scratch", vm.StatusMessage);
        mockClient.Verify(c => c.DeleteMemoryAsync("mem_005", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task BackupAndRestore_CallsExpectedApiEndpoints()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var backup = new MemoryBackupInfoDto
        {
            BackupPath = "backups/mem_auto.db",
            FileSizeBytes = 12345,
            RecordCount = 5,
        };

        mockClient
            .Setup(c => c.CreateMemoryBackupAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(backup);
        mockClient
            .Setup(c => c.RestoreMemoryBackupAsync("backups/mem_auto.db", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        mockClient
            .Setup(c => c.ListMemoriesAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), 100, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryRecordDto>());
        mockClient
            .Setup(c => c.ListMemoryAuditAsync(It.IsAny<string?>(), 50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryAuditEntryDto>());
        mockClient
            .Setup(c => c.ListMemoryBackupsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<MemoryBackupInfoDto> { backup });

        var vm = new MemoryViewModel(mockClient.Object);
        await vm.CreateBackupCommand.ExecuteAsync(null);

        Assert.Contains("Created backup with 5 records", vm.StatusMessage);

        await vm.RestoreBackupCommand.ExecuteAsync("backups/mem_auto.db");
        Assert.Equal("Database successfully restored from backup.", vm.StatusMessage);
        mockClient.Verify(c => c.RestoreMemoryBackupAsync("backups/mem_auto.db", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ExportMemoriesAsync_SetsExportResult()
    {
        var mockClient = new Mock<INexoraApiClient>();
        mockClient
            .Setup(c => c.ExportMemoriesAsync("json", It.IsAny<CancellationToken>()))
            .ReturnsAsync("[{\"id\":\"mem_001\"}]");

        var vm = new MemoryViewModel(mockClient.Object);
        await vm.ExportMemoriesCommand.ExecuteAsync("json");

        Assert.Equal("[{\"id\":\"mem_001\"}]", vm.ExportResult);
        Assert.Contains("Export complete (18 characters).", vm.StatusMessage);
    }
}
