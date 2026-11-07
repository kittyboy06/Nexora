using System;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class ApprovalViewModelTests
{
    [Fact]
    public async Task ApproveCommand_CallsDecideApprovalWithTrue()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var approval = new ActionApproval(
            ApprovalId: "appr_test",
            TaskId: "task_test",
            StepId: 2,
            ToolName: "terminal_run_script",
            ArgumentHash: "hashabc",
            ExpiresAt: DateTimeOffset.UtcNow.AddMinutes(10)
        );

        var returnedTask = new AgentTask(TaskId: "task_test", Prompt: "p", Status: Models.TaskStatus.EXECUTING);

        mockClient
            .Setup(c => c.DecideApprovalAsync("task_test", "appr_test", true, It.IsAny<CancellationToken>()))
            .ReturnsAsync(returnedTask);

        var vm = new ApprovalDialogViewModel(mockClient.Object);
        vm.SetApproval(approval);

        AgentTask? resultTask = null;
        vm.DecisionCompleted += t => resultTask = t;

        await vm.ApproveCommand.ExecuteAsync(null);

        Assert.NotNull(resultTask);
        Assert.Equal("task_test", resultTask.TaskId);
        Assert.Equal(Models.TaskStatus.EXECUTING, resultTask.Status);
        mockClient.Verify(c => c.DecideApprovalAsync("task_test", "appr_test", true, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task RejectCommand_CallsDecideApprovalWithFalse()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var approval = new ActionApproval(
            ApprovalId: "appr_test",
            TaskId: "task_test",
            StepId: 2,
            ToolName: "terminal_run_script",
            ArgumentHash: "hashabc",
            ExpiresAt: DateTimeOffset.UtcNow.AddMinutes(10)
        );

        var returnedTask = new AgentTask(TaskId: "task_test", Prompt: "p", Status: Models.TaskStatus.FAILED);

        mockClient
            .Setup(c => c.DecideApprovalAsync("task_test", "appr_test", false, It.IsAny<CancellationToken>()))
            .ReturnsAsync(returnedTask);

        var vm = new ApprovalDialogViewModel(mockClient.Object);
        vm.SetApproval(approval);

        await vm.RejectCommand.ExecuteAsync(null);

        mockClient.Verify(c => c.DecideApprovalAsync("task_test", "appr_test", false, It.IsAny<CancellationToken>()), Times.Once);
    }
}
