using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class GeneratedToolsViewModelTests
{
    [Fact]
    public async Task LoadAllAsync_PopulatesToolsAndEvidence()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleTools = new List<GeneratedToolRecordDto>
        {
            new()
            {
                Manifest = new GeneratedToolManifestDto { Name = "math_util", Version = "1.0.0", Description = "Math utility" },
                IsEnabled = true,
            },
        };
        var sampleEvidence = new List<SandboxRunResultDto>
        {
            new()
            {
                RunId = "run_abc123",
                ToolName = "math_util",
                Status = "TESTS_PASSED",
                ExecutionTimeMs = 12.5,
                PeakMemoryBytes = 18000000,
            },
        };

        mockClient
            .Setup(c => c.ListGeneratedToolsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(sampleTools);
        mockClient
            .Setup(c => c.ListSandboxEvidenceAsync(50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(sampleEvidence);

        var vm = new GeneratedToolsViewModel(mockClient.Object);
        await vm.LoadAllCommand.ExecuteAsync(null);

        Assert.Single(vm.Tools);
        Assert.Equal("math_util", vm.Tools[0].Manifest.Name);
        Assert.Single(vm.EvidenceRuns);
        Assert.Equal("run_abc123", vm.EvidenceRuns[0].RunId);
        Assert.Contains("Loaded 1 tools, 1 evidence records", vm.StatusMessage);
    }

    [Fact]
    public async Task ValidateProposalAsync_UpdatesValidationReport()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var report = new ToolValidationReportDto
        {
            IsValid = true,
            SourceSha256 = "sha256abc",
        };

        mockClient
            .Setup(c => c.ValidateToolProposalAsync(It.IsAny<GeneratedToolProposalDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(report);

        var vm = new GeneratedToolsViewModel(mockClient.Object)
        {
            ProposalName = "text_cleaner",
            ProposalDescription = "Cleans whitespace",
            ProposalCode = "def text_cleaner(s: str) -> str: return s.strip()",
        };

        await vm.ValidateProposalCommand.ExecuteAsync(null);

        Assert.NotNull(vm.LatestValidationReport);
        Assert.True(vm.LatestValidationReport.IsValid);
        Assert.Contains("AST Security Validation Passed", vm.StatusMessage);
    }

    [Fact]
    public async Task RunTrialAsync_ExecutesSandboxAndRefreshesEvidence()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var trialResult = new SandboxRunResultDto
        {
            RunId = "run_trial_999",
            ToolName = "text_cleaner",
            Status = "TESTS_PASSED",
            ExecutionTimeMs = 15.0,
            PeakMemoryBytes = 16000000,
        };

        mockClient
            .Setup(c => c.RunSandboxTrialAsync(It.IsAny<TrialRunRequestDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(trialResult);
        mockClient
            .Setup(c => c.ListSandboxEvidenceAsync(50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SandboxRunResultDto> { trialResult });

        var vm = new GeneratedToolsViewModel(mockClient.Object)
        {
            ProposalName = "text_cleaner",
            ProposalDescription = "Cleans whitespace",
            ProposalCode = "def text_cleaner(s: str) -> str: return s.strip()",
        };

        await vm.RunTrialCommand.ExecuteAsync(null);

        Assert.NotNull(vm.LatestTrialResult);
        Assert.Equal("TESTS_PASSED", vm.LatestTrialResult.Status);
        Assert.Single(vm.EvidenceRuns);
        Assert.Equal("run_trial_999", vm.EvidenceRuns[0].RunId);
    }

    [Fact]
    public async Task PromoteProposalAsync_PromotesWhenTrialPassed()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var trialResult = new SandboxRunResultDto
        {
            RunId = "run_trial_999",
            ToolName = "text_cleaner",
            Status = "TESTS_PASSED",
        };
        var promotedRecord = new GeneratedToolRecordDto
        {
            Manifest = new GeneratedToolManifestDto { Name = "text_cleaner", Version = "1.0.0", Description = "Cleans whitespace" },
            IsEnabled = true,
        };

        mockClient
            .Setup(c => c.PromoteToolAsync(It.IsAny<ToolPromotionRequestDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(promotedRecord);
        mockClient
            .Setup(c => c.ListGeneratedToolsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<GeneratedToolRecordDto> { promotedRecord });
        mockClient
            .Setup(c => c.ListSandboxEvidenceAsync(50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SandboxRunResultDto> { trialResult });

        var vm = new GeneratedToolsViewModel(mockClient.Object)
        {
            ProposalName = "text_cleaner",
            ProposalDescription = "Cleans whitespace",
            ProposalCode = "def text_cleaner(s: str) -> str: return s.strip()",
            LatestTrialResult = trialResult,
        };

        await vm.PromoteProposalCommand.ExecuteAsync(null);

        Assert.Contains("Successfully promoted 'text_cleaner'", vm.StatusMessage);
        Assert.Single(vm.Tools);
        Assert.Equal("text_cleaner", vm.Tools[0].Manifest.Name);
    }

    [Fact]
    public async Task ToggleToolEnabledAsync_UpdatesEnabledState()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleTool = new GeneratedToolRecordDto
        {
            Manifest = new GeneratedToolManifestDto { Name = "text_cleaner" },
            IsEnabled = true,
        };
        var updatedTool = new GeneratedToolRecordDto
        {
            Manifest = new GeneratedToolManifestDto { Name = "text_cleaner" },
            IsEnabled = false,
        };

        mockClient
            .Setup(c => c.UpdateGeneratedToolAsync("text_cleaner", It.IsAny<ToolUpdateRequestDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(updatedTool);

        var vm = new GeneratedToolsViewModel(mockClient.Object);
        await vm.ToggleToolEnabledCommand.ExecuteAsync(sampleTool);

        Assert.False(sampleTool.IsEnabled);
        Assert.Contains("Disabled", vm.StatusMessage);
    }

    [Fact]
    public async Task DeleteToolAsync_RemovesToolFromCatalog()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleTool = new GeneratedToolRecordDto
        {
            Manifest = new GeneratedToolManifestDto { Name = "text_cleaner" },
        };

        mockClient
            .Setup(c => c.DeleteGeneratedToolAsync("text_cleaner", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        mockClient
            .Setup(c => c.ListGeneratedToolsAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<GeneratedToolRecordDto>());
        mockClient
            .Setup(c => c.ListSandboxEvidenceAsync(50, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SandboxRunResultDto>());

        var vm = new GeneratedToolsViewModel(mockClient.Object);
        await vm.DeleteToolCommand.ExecuteAsync(sampleTool);

        Assert.Contains("Deleted tool text_cleaner", vm.StatusMessage);
        Assert.Empty(vm.Tools);
    }
}
