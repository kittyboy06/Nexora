using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class ResearchViewModelTests
{
    [Fact]
    public async Task RefreshResearchAsync_PopulatesEvidenceAndQuarantine()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var mockPoller = new Mock<ITaskPoller>();

        var evidence = new List<ResearchEvidenceDto>
        {
            new()
            {
                EvidenceId = "ev_001",
                TaskId = "t_100",
                Title = "Python Docs",
                Url = "https://python.org",
                ContentSnippet = "Python language reference",
                ContentHash = "hash111",
                Engine = "http",
            }
        };

        var downloads = new List<QuarantineItemDto>
        {
            new()
            {
                TaskId = "t_100",
                Filename = "specs.pdf",
                OriginalUrl = "https://example.com/specs.pdf",
                FileSize = 5000,
                Sha256Hash = "hash222",
            }
        };

        mockClient
            .Setup(c => c.ListTaskEvidenceAsync("t_100", It.IsAny<CancellationToken>()))
            .ReturnsAsync(evidence);
        mockClient
            .Setup(c => c.ListQuarantinedDownloadsAsync("t_100", It.IsAny<CancellationToken>()))
            .ReturnsAsync(downloads);

        var vm = new TaskDetailViewModel(mockClient.Object, mockPoller.Object);
        var task = new AgentTask(TaskId: "t_100", Prompt: "Research task");

        vm.LoadTask(task);
        await vm.RefreshResearchAsync();

        Assert.True(vm.HasResearchEvidence);
        Assert.Single(vm.ResearchEvidence);
        Assert.Equal("Python Docs", vm.ResearchEvidence[0].Title);

        Assert.True(vm.HasQuarantinedDownloads);
        Assert.Single(vm.QuarantinedDownloads);
        Assert.Equal("specs.pdf", vm.QuarantinedDownloads[0].Filename);
    }

    [Fact]
    public async Task RefreshResearchAsync_WhenTaskNull_ClearsCollections()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var mockPoller = new Mock<ITaskPoller>();

        var vm = new TaskDetailViewModel(mockClient.Object, mockPoller.Object);
        await vm.RefreshResearchAsync();

        Assert.False(vm.HasResearchEvidence);
        Assert.Empty(vm.ResearchEvidence);
        Assert.False(vm.HasQuarantinedDownloads);
        Assert.Empty(vm.QuarantinedDownloads);
    }
}
