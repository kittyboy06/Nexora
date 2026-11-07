using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class SchedulerViewModelTests
{
    [Fact]
    public async Task LoadSchedulesAsync_PopulatesSchedulesAndRecentRuns()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var schedules = new List<ScheduleDto>
        {
            new()
            {
                Id = "sched-1",
                Name = "Daily Morning Brief",
                PromptTemplate = "Summarize emails and events",
                TriggerType = TriggerType.CRON,
                TriggerExpression = "0 9 * * *",
                Timezone = "America/New_York",
                Status = ScheduleStatus.ACTIVE
            },
            new()
            {
                Id = "sched-2",
                Name = "Health Heartbeat",
                PromptTemplate = "Check system resources",
                TriggerType = TriggerType.INTERVAL,
                TriggerExpression = "15m",
                Timezone = "UTC",
                Status = ScheduleStatus.PAUSED
            }
        };

        var runs = new List<ScheduleRunDto>
        {
            new()
            {
                RunId = "run-101",
                ScheduleId = "sched-1",
                RunKey = "sched-1:2026-11-07T09:00:00Z",
                Status = RunStatus.COMPLETED,
                ScheduledFor = DateTime.UtcNow
            }
        };

        mockClient
            .Setup(c => c.ListSchedulesAsync(It.IsAny<string?>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(schedules);
        mockClient
            .Setup(c => c.ListScheduleRunsAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(runs);

        var vm = new SchedulerViewModel(mockClient.Object);
        await vm.LoadSchedulesCommand.ExecuteAsync(null);

        Assert.Equal(2, vm.Schedules.Count);
        Assert.Single(vm.ScheduleRuns);
        Assert.Contains("Loaded 2 schedules", vm.StatusMessage);
    }

    [Fact]
    public async Task CreateScheduleAsync_ValidatesInputAndAddsToCollection()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var createdDto = new ScheduleDto
        {
            Id = "sched-new-1",
            Name = "Hourly Audit",
            PromptTemplate = "Audit system logs",
            TriggerType = TriggerType.INTERVAL,
            TriggerExpression = "1h",
            Timezone = "UTC",
            Status = ScheduleStatus.ACTIVE
        };

        mockClient
            .Setup(c => c.CreateScheduleAsync(It.IsAny<ScheduleCreateRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(createdDto);

        var vm = new SchedulerViewModel(mockClient.Object);

        // 1. Missing name -> validation error
        vm.FormName = "";
        vm.FormPromptTemplate = "Do something";
        vm.FormTriggerExpression = "1h";
        await vm.CreateScheduleCommand.ExecuteAsync(null);
        Assert.Contains("required", vm.ErrorMessage);
        Assert.Empty(vm.Schedules);

        // 2. Valid input
        vm.FormName = "Hourly Audit";
        vm.FormPromptTemplate = "Audit system logs";
        vm.FormTriggerExpression = "1h";
        await vm.CreateScheduleCommand.ExecuteAsync(null);

        Assert.Single(vm.Schedules);
        Assert.Equal("sched-new-1", vm.Schedules[0].Id);
        Assert.Equal("Hourly Audit", vm.Schedules[0].Name);
        Assert.Contains("created successfully", vm.StatusMessage);
    }

    [Fact]
    public async Task TogglePauseAsync_PausesAndResumesSchedule()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var activeSched = new ScheduleDto
        {
            Id = "sched-toggle",
            Name = "Toggle Test",
            Status = ScheduleStatus.ACTIVE
        };
        var pausedSched = new ScheduleDto
        {
            Id = "sched-toggle",
            Name = "Toggle Test",
            Status = ScheduleStatus.PAUSED
        };

        mockClient
            .Setup(c => c.PauseScheduleAsync("sched-toggle", It.IsAny<CancellationToken>()))
            .ReturnsAsync(pausedSched);
        mockClient
            .Setup(c => c.ResumeScheduleAsync("sched-toggle", It.IsAny<CancellationToken>()))
            .ReturnsAsync(activeSched);

        var vm = new SchedulerViewModel(mockClient.Object);
        vm.Schedules.Add(activeSched);
        vm.SelectedSchedule = activeSched;

        // Toggle from Active -> Paused
        await vm.TogglePauseCommand.ExecuteAsync(activeSched);
        Assert.Equal(ScheduleStatus.PAUSED, vm.Schedules[0].Status);
        Assert.Contains("paused", vm.StatusMessage);

        // Toggle from Paused -> Active
        await vm.TogglePauseCommand.ExecuteAsync(vm.Schedules[0]);
        Assert.Equal(ScheduleStatus.ACTIVE, vm.Schedules[0].Status);
        Assert.Contains("resumed", vm.StatusMessage);
    }

    [Fact]
    public async Task RunNowAsync_TriggersImmediateRunAndPrependsToHistory()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var schedule = new ScheduleDto
        {
            Id = "sched-run-now",
            Name = "On Demand Job",
            Status = ScheduleStatus.ACTIVE
        };
        var runResult = new ScheduleRunDto
        {
            RunId = "run-manual-001",
            ScheduleId = "sched-run-now",
            RunKey = "sched-run-now:manual",
            Status = RunStatus.DISPATCHED,
            ScheduledFor = DateTime.UtcNow
        };

        mockClient
            .Setup(c => c.TriggerScheduleAsync("sched-run-now", It.IsAny<CancellationToken>()))
            .ReturnsAsync(runResult);

        var vm = new SchedulerViewModel(mockClient.Object);
        vm.Schedules.Add(schedule);

        await vm.RunNowCommand.ExecuteAsync(schedule);

        Assert.Single(vm.ScheduleRuns);
        Assert.Equal("run-manual-001", vm.ScheduleRuns[0].RunId);
        Assert.Contains("Triggered immediate run", vm.StatusMessage);
    }

    [Fact]
    public async Task DeleteScheduleAsync_RemovesFromCollectionAndResetsSelection()
    {
        var mockClient = new Mock<INexoraApiClient>();
        var schedule = new ScheduleDto
        {
            Id = "sched-del",
            Name = "To Delete",
            Status = ScheduleStatus.PAUSED
        };

        mockClient
            .Setup(c => c.DeleteScheduleAsync("sched-del", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        mockClient
            .Setup(c => c.ListScheduleRunsAsync(It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ScheduleRunDto>());

        var vm = new SchedulerViewModel(mockClient.Object);
        vm.Schedules.Add(schedule);
        vm.SelectedSchedule = schedule;

        await vm.DeleteScheduleCommand.ExecuteAsync(schedule);

        Assert.Empty(vm.Schedules);
        Assert.Null(vm.SelectedSchedule);
        Assert.Contains("deleted", vm.StatusMessage);
    }
}
