using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class SkillsViewModelTests
{
    [Fact]
    public async Task LoadInstalledSkillsAsync_PopulatesCollection()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleSkills = new List<SkillSummaryDto>
        {
            new() { Id = "docker-pro", Name = "Docker Pro", Version = "1.0.0", IsEnabled = true },
            new() { Id = "git-expert", Name = "Git Expert", Version = "2.1.0", IsEnabled = true },
        };

        mockClient
            .Setup(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(sampleSkills);

        var vm = new SkillsViewModel(mockClient.Object);
        await vm.LoadInstalledSkillsCommand.ExecuteAsync(null);

        Assert.Equal(2, vm.InstalledSkills.Count);
        Assert.Equal("docker-pro", vm.InstalledSkills[0].Id);
        Assert.Equal("git-expert", vm.InstalledSkills[1].Id);
        mockClient.Verify(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ToggleSkillAsync_CallsPatchSkill()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var skill = new SkillSummaryDto { Id = "pytest-pro", Name = "Pytest Pro", IsEnabled = true };

        var updatedBundle = new SkillBundleDto
        {
            Manifest = new SkillManifestDto { Id = "pytest-pro", Name = "Pytest Pro" },
            IsEnabled = false,
        };

        mockClient
            .Setup(c => c.PatchSkillAsync("pytest-pro", false, null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(updatedBundle);
        mockClient
            .Setup(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SkillSummaryDto> { skill });

        var vm = new SkillsViewModel(mockClient.Object);
        await vm.ToggleSkillCommand.ExecuteAsync(skill);

        mockClient.Verify(c => c.PatchSkillAsync("pytest-pro", false, null, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task InspectSkillAsync_LoadsBundleAndMarkdown()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var skill = new SkillSummaryDto { Id = "k8s-operator", Name = "K8s Operator", Version = "1.0.0" };
        var bundle = new SkillBundleDto
        {
            Manifest = new SkillManifestDto { Id = "k8s-operator", Name = "K8s Operator", Version = "1.0.0" },
            Provenance = new SkillProvenanceDto { SourceUrl = "local", SkillSha256 = "abc123hash" },
            Instructions = "# K8s Instructions\nDeploy with Helm.",
        };

        mockClient
            .Setup(c => c.GetSkillAsync("k8s-operator", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(bundle);

        var vm = new SkillsViewModel(mockClient.Object);
        await vm.InspectSkillCommand.ExecuteAsync(skill);

        Assert.NotNull(vm.InspectedBundle);
        Assert.Equal("k8s-operator", vm.InspectedBundle.Manifest.Id);
        Assert.Equal("# K8s Instructions\nDeploy with Helm.", vm.MarkdownPreview);
    }

    [Fact]
    public async Task SearchGitHubAsync_PopulatesDiscoveryCandidates()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var candidates = new List<SkillDiscoveryCandidateDto>
        {
            new() { Owner = "nexora-community", Repo = "docker-workflow", Stars = 142 },
        };

        mockClient
            .Setup(c => c.SearchDiscoveryAsync("docker", 1, 10, It.IsAny<CancellationToken>()))
            .ReturnsAsync(candidates);
        mockClient
            .Setup(c => c.GetGitHubRateLimitAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(new GitHubRateLimitStatusDto { Remaining = 58, Limit = 60 });

        var vm = new SkillsViewModel(mockClient.Object)
        {
            SearchQuery = "docker",
        };

        await vm.SearchGitHubCommand.ExecuteAsync(null);

        Assert.Single(vm.DiscoveryCandidates);
        Assert.Equal("docker-workflow", vm.DiscoveryCandidates[0].Repo);
        Assert.Equal(142, vm.DiscoveryCandidates[0].Stars);
    }

    [Fact]
    public async Task InstallCandidateAsync_InvokesApiAndRefreshes()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var candidate = new SkillDiscoveryCandidateDto
        {
            Owner = "nexora-community",
            Repo = "react-patterns",
            DefaultBranch = "main",
        };

        var installedBundle = new SkillBundleDto
        {
            Manifest = new SkillManifestDto { Id = "react-patterns", Name = "React Patterns", Version = "1.0.0" },
        };

        mockClient
            .Setup(c => c.InstallSkillAsync(It.Is<InstallSkillRequestDto>(r => r.Owner == "nexora-community" && r.Repo == "react-patterns"), It.IsAny<CancellationToken>()))
            .ReturnsAsync(installedBundle);
        mockClient
            .Setup(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SkillSummaryDto>());

        var vm = new SkillsViewModel(mockClient.Object);
        await vm.InstallCandidateCommand.ExecuteAsync(candidate);

        mockClient.Verify(c => c.InstallSkillAsync(It.IsAny<InstallSkillRequestDto>(), It.IsAny<CancellationToken>()), Times.Once);
        mockClient.Verify(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ImportFromFolderAsync_CallsApiAndRefreshes()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleBundle = new SkillBundleDto
        {
            Manifest = new SkillManifestDto { Id = "local-git", Name = "Local Git", Version = "1.0.0" },
            IsEnabled = false,
        };

        mockClient
            .Setup(c => c.ImportSkillFolderAsync(It.Is<SkillImportFolderRequestDto>(r => r.FolderPath == "C:\\skills\\git"), It.IsAny<CancellationToken>()))
            .ReturnsAsync(sampleBundle);
        mockClient
            .Setup(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SkillSummaryDto>());

        var vm = new SkillsViewModel(mockClient.Object)
        {
            ImportFolderPath = "C:\\skills\\git",
            EnableOnImport = false,
        };

        await vm.ImportFromFolderCommand.ExecuteAsync(null);

        mockClient.Verify(c => c.ImportSkillFolderAsync(It.IsAny<SkillImportFolderRequestDto>(), It.IsAny<CancellationToken>()), Times.Once);
        mockClient.Verify(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()), Times.Once);
        Assert.Contains("Imported 'Local Git'", vm.StatusMessage);
    }

    [Fact]
    public async Task ImportFromPasteAsync_CallsApiAndRefreshes()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var sampleBundle = new SkillBundleDto
        {
            Manifest = new SkillManifestDto { Id = "pasted-tool", Name = "Pasted Tool", Version = "1.0.0" },
            IsEnabled = false,
        };

        mockClient
            .Setup(c => c.ImportSkillPasteAsync(It.IsAny<SkillImportPasteRequestDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(sampleBundle);
        mockClient
            .Setup(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<SkillSummaryDto>());

        var vm = new SkillsViewModel(mockClient.Object)
        {
            ImportManifestYaml = "id: pasted-tool\nname: Pasted Tool\nversion: 1.0.0\n",
            ImportInstructions = "# Instructions\nDo something safe.",
            EnableOnImport = false,
        };

        await vm.ImportFromPasteCommand.ExecuteAsync(null);

        mockClient.Verify(c => c.ImportSkillPasteAsync(It.IsAny<SkillImportPasteRequestDto>(), It.IsAny<CancellationToken>()), Times.Once);
        mockClient.Verify(c => c.ListSkillsAsync(false, null, It.IsAny<CancellationToken>()), Times.Once);
        Assert.Contains("Pasted skill 'Pasted Tool' imported", vm.StatusMessage);
    }

    [Fact]
    public async Task PreviewReadmeAsync_SetsSanitizedMarkdown()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var candidate = new SkillDiscoveryCandidateDto
        {
            Owner = "octocat",
            Repo = "hello-world",
            DefaultBranch = "main",
        };

        mockClient
            .Setup(c => c.PreviewSkillReadmeAsync("octocat", "hello-world", "main", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new SkillReadmePreviewResponseDto
            {
                Owner = "octocat",
                Repo = "hello-world",
                Branch = "main",
                SanitizedMarkdown = "# Hello World\nClean description.",
                Length = 32,
            });

        var vm = new SkillsViewModel(mockClient.Object);
        await vm.PreviewReadmeCommand.ExecuteAsync(candidate);

        Assert.Equal("# Hello World\nClean description.", vm.ReadmePreview);
        Assert.Contains("README loaded", vm.StatusMessage);
    }
}
