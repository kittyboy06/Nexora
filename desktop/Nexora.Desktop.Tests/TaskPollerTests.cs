using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Xunit;

namespace Nexora.Desktop.Tests;

public class TaskPollerTests
{
    [Fact]
    public async Task TaskPoller_FiresUpdatedAndStopsOnTerminalState()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var taskSequence = new Queue<AgentTask>(new[]
        {
            new AgentTask(TaskId: "t1", Prompt: "p", Status: Models.TaskStatus.PLANNING),
            new AgentTask(TaskId: "t1", Prompt: "p", Status: Models.TaskStatus.EXECUTING),
            new AgentTask(TaskId: "t1", Prompt: "p", Status: Models.TaskStatus.COMPLETED),
        });

        mockClient
            .Setup(c => c.GetTaskAsync("t1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(() => taskSequence.Dequeue());

        using var poller = new TaskPoller(mockClient.Object);
        var updatedCount = 0;
        var terminalReached = false;

        poller.TaskUpdated += t => updatedCount++;
        poller.TerminalStateReached += t => terminalReached = true;

        poller.StartPolling("t1", TimeSpan.FromMilliseconds(50));

        // Wait up to 1 second for polling to finish
        var timeout = DateTime.UtcNow.AddSeconds(1);
        while (poller.IsPolling && DateTime.UtcNow < timeout)
        {
            await Task.Delay(50);
        }

        Assert.False(poller.IsPolling);
        Assert.True(terminalReached);
        Assert.True(updatedCount >= 2);
    }

    [Fact]
    public async Task TaskPoller_FiresApprovalRequiredOnWaitingApproval()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var waitingTask = new AgentTask(
            TaskId: "t2",
            Prompt: "Delete file",
            Status: Models.TaskStatus.WAITING_APPROVAL,
            PendingApproval: new ActionApproval(
                ApprovalId: "appr_1",
                TaskId: "t2",
                StepId: 1,
                ToolName: "file_delete",
                ArgumentHash: "hash123",
                ExpiresAt: DateTimeOffset.UtcNow.AddMinutes(10)
            )
        );

        mockClient
            .Setup(c => c.GetTaskAsync("t2", It.IsAny<CancellationToken>()))
            .ReturnsAsync(waitingTask);

        using var poller = new TaskPoller(mockClient.Object);
        var approvalFired = false;

        poller.ApprovalRequired += t =>
        {
            approvalFired = true;
            poller.StopPolling();
        };

        poller.StartPolling("t2", TimeSpan.FromMilliseconds(50));

        var timeout = DateTime.UtcNow.AddSeconds(1);
        while (poller.IsPolling && DateTime.UtcNow < timeout)
        {
            await Task.Delay(50);
        }

        Assert.True(approvalFired);
    }
}
