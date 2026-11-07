using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class McpViewModelTests
{
    [Fact]
    public async Task LoadServersAsync_PopulatesServersCollection()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleServers = new List<McpServerRecordDto>
        {
            new()
            {
                Config = new McpServerConfigDto { Id = "filesystem", Name = "Filesystem Server", Command = "npx" },
                Status = "STOPPED",
            },
            new()
            {
                Config = new McpServerConfigDto { Id = "brave-search", Name = "Brave Search", Command = "uvx" },
                Status = "DISCOVERED",
            },
        };

        mockClient
            .Setup(c => c.ListMcpServersAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(sampleServers);

        var vm = new McpViewModel(mockClient.Object);
        await vm.LoadServersCommand.ExecuteAsync(null);

        Assert.Equal(2, vm.Servers.Count);
        Assert.Equal("filesystem", vm.Servers[0].Config.Id);
        Assert.Equal("brave-search", vm.Servers[1].Config.Id);
        Assert.Contains("Loaded 2 MCP servers", vm.StatusMessage);
        mockClient.Verify(c => c.ListMcpServersAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ApproveServerAsync_CallsApproveEndpointAndUpdatesStatus()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var approvedRecord = new McpServerRecordDto
        {
            Config = new McpServerConfigDto { Id = "test-srv", Name = "Test Server", IsApproved = true },
            Status = "APPROVED",
        };

        mockClient
            .Setup(c => c.ApproveMcpServerAsync("test-srv", It.IsAny<CancellationToken>()))
            .ReturnsAsync(approvedRecord);

        var vm = new McpViewModel(mockClient.Object);
        vm.Servers.Add(new McpServerRecordDto
        {
            Config = new McpServerConfigDto { Id = "test-srv", Name = "Test Server", IsApproved = false },
            Status = "DISCOVERED",
        });

        await vm.ApproveServerCommand.ExecuteAsync("test-srv");

        mockClient.Verify(c => c.ApproveMcpServerAsync("test-srv", It.IsAny<CancellationToken>()), Times.Once);
        Assert.Equal("APPROVED", vm.Servers[0].Status);
        Assert.True(vm.Servers[0].Config.IsApproved);
    }

    [Fact]
    public async Task ConnectServerAsync_CallsConnectAndUpdatesAdvertisedTools()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var connectedRecord = new McpServerRecordDto
        {
            Config = new McpServerConfigDto { Id = "sqlite", Name = "SQLite MCP", IsApproved = true },
            Status = "CONNECTED",
            AdvertisedTools = new List<McpToolDefinitionDto>
            {
                new() { Name = "read_query", Description = "Execute SELECT", RiskLevel = "CONTROLLED" },
            },
        };

        mockClient
            .Setup(c => c.ConnectMcpServerAsync("sqlite", It.IsAny<CancellationToken>()))
            .ReturnsAsync(connectedRecord);

        var vm = new McpViewModel(mockClient.Object);
        var initial = new McpServerRecordDto
        {
            Config = new McpServerConfigDto { Id = "sqlite", Name = "SQLite MCP", IsApproved = true },
            Status = "APPROVED",
        };
        vm.Servers.Add(initial);
        vm.SelectServer(initial);

        await vm.ConnectServerCommand.ExecuteAsync("sqlite");

        mockClient.Verify(c => c.ConnectMcpServerAsync("sqlite", It.IsAny<CancellationToken>()), Times.Once);
        Assert.Equal("CONNECTED", vm.Servers[0].Status);
        Assert.Single(vm.AdvertisedTools);
        Assert.Equal("read_query", vm.AdvertisedTools[0].Name);
    }

    [Fact]
    public async Task PingServerAsync_SetsLatencyText()
    {
        var mockClient = new Mock<INexoraApiClient>();
        mockClient
            .Setup(c => c.PingMcpServerAsync("sqlite", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new McpPingResponseDto { Status = "pong", LatencyMs = 12.4 });

        var vm = new McpViewModel(mockClient.Object);
        await vm.PingServerCommand.ExecuteAsync("sqlite");

        Assert.Equal("12.4 ms", vm.PingLatencyText);
        Assert.Contains("12.4 ms", vm.StatusMessage);
    }

    [Fact]
    public async Task SaveSecretAsync_EncryptsAndAddsToVault()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var savedSummary = new McpVaultItemSummaryDto
        {
            Key = "GITHUB_TOKEN",
            Description = "GitHub PAT",
            CreatedAt = "2026-11-07T12:00:00Z",
            HasValue = true,
        };

        mockClient
            .Setup(c => c.WriteMcpVaultSecretAsync(It.IsAny<McpVaultWriteRequestDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(savedSummary);

        var vm = new McpViewModel(mockClient.Object)
        {
            NewSecretKey = "GITHUB_TOKEN",
            NewSecretValue = "ghp_secrettoken123",
            NewSecretDescription = "GitHub PAT",
        };

        await vm.SaveSecretCommand.ExecuteAsync(null);

        mockClient.Verify(c => c.WriteMcpVaultSecretAsync(
            It.Is<McpVaultWriteRequestDto>(r => r.Key == "GITHUB_TOKEN" && r.SecretValue == "ghp_secrettoken123"),
            It.IsAny<CancellationToken>()), Times.Once);

        Assert.Single(vm.VaultSecrets);
        Assert.Equal("GITHUB_TOKEN", vm.VaultSecrets[0].Key);
        // Value field cleared for security
        Assert.Empty(vm.NewSecretValue);
    }

    [Fact]
    public async Task DeleteSecretAsync_RemovesFromVault()
    {
        var mockClient = new Mock<INexoraApiClient>();
        mockClient
            .Setup(c => c.DeleteMcpVaultSecretAsync("API_KEY", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var vm = new McpViewModel(mockClient.Object);
        vm.VaultSecrets.Add(new McpVaultItemSummaryDto { Key = "API_KEY", Description = "Old key" });

        await vm.DeleteSecretCommand.ExecuteAsync("API_KEY");

        mockClient.Verify(c => c.DeleteMcpVaultSecretAsync("API_KEY", It.IsAny<CancellationToken>()), Times.Once);
        Assert.Empty(vm.VaultSecrets);
    }
}
