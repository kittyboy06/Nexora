using System.Collections.Generic;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Nexora.Desktop.ViewModels;
using Xunit;

namespace Nexora.Desktop.Tests;

public class FleetViewModelTests
{
    private class DummyApiClient : INexoraApiClient
    {
        public System.Threading.Tasks.Task<HealthResponse> GetHealthAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<OllamaStatusResponse> GetOllamaStatusAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<ModelProfileListResponse> GetModelProfilesAsync(bool refresh = false, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> CreateTaskAsync(string prompt, string? profileId = null, string? executionMode = "auto", System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> GetTaskAsync(string taskId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<IReadOnlyList<AgentTask>> ListTasksAsync(System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> CancelTaskAsync(string taskId, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
        public System.Threading.Tasks.Task<AgentTask> DecideApprovalAsync(string taskId, string approvalId, bool approved, System.Threading.CancellationToken cancellationToken = default) => throw new System.NotImplementedException();
    }

    private class DummyPoller : ITaskPoller
    {
        public bool IsPolling => false;
        public string? CurrentTaskId => null;
        public event System.Action<AgentTask>? TaskUpdated;
        public event System.Action<AgentTask>? TerminalStateReached;
        public event System.Action<AgentTask>? ApprovalRequired;
        public void StartPolling(string taskId, System.TimeSpan? interval = null) { }
        public void StopPolling() { }
        public void Dispose() { }
    }

    [Fact]
    public void FleetNodeViewModel_StatusBadgeMappings()
    {
        var node = new FleetNodeViewModel
        {
            NodeId = "n1",
            Role = "researcher",
            Objective = "Read files",
            State = FleetNodeState.RUNNING,
        };

        Assert.Equal("● Running", node.StatusBadgeText);
        Assert.Equal("#0078D4", node.StatusColor);
        Assert.True(node.IsRunning);
        Assert.False(node.IsCompleted);

        node.State = FleetNodeState.COMPLETED;
        Assert.Equal("✓ Done", node.StatusBadgeText);
        Assert.Equal("#107C41", node.StatusColor);
        Assert.True(node.IsCompleted);
        Assert.False(node.IsRunning);

        node.State = FleetNodeState.BLOCKED;
        Assert.Equal("⊘ Blocked", node.StatusBadgeText);
        Assert.Equal("#A80000", node.StatusColor);
        Assert.True(node.IsBlocked);
    }

    [Fact]
    public void TaskDetailViewModel_PopulatesFleetNodes_FromFleetPlan()
    {
        var poller = new DummyPoller();
        var client = new DummyApiClient();
        var vm = new TaskDetailViewModel(client, poller);

        Assert.False(vm.HasFleetNodes);

        var node1 = new FleetNodeModel(
            NodeId: "n1",
            Role: "planner",
            Objective: "Decompose task",
            State: FleetNodeState.COMPLETED
        );
        var node2 = new FleetNodeModel(
            NodeId: "n2",
            Role: "coder",
            Objective: "Write implementation",
            Dependencies: new List<string> { "n1" },
            State: FleetNodeState.RUNNING
        );

        var fleetPlan = new FleetPlanModel(
            FleetId: "f1",
            ParentTaskId: "t1",
            Goal: "Complete feature",
            Nodes: new Dictionary<string, FleetNodeModel>
            {
                ["n1"] = node1,
                ["n2"] = node2,
            }
        );

        var artifact = new ArtifactModel(
            ArtifactId: "art_1",
            NodeId: "n1",
            ProducerRole: "planner",
            SchemaVersion: "1.0",
            Content: "plan completed",
            ContentHash: "hash123"
        );

        var task = new AgentTask(
            TaskId: "t1",
            Prompt: "Do feature",
            FleetPlan: fleetPlan,
            Artifacts: new List<ArtifactModel> { artifact }
        );

        vm.LoadTask(task);

        Assert.True(vm.HasFleetNodes);
        Assert.Equal(2, vm.FleetNodes.Count);
        Assert.Equal("n1", vm.FleetNodes[0].NodeId);
        Assert.Equal("planner", vm.FleetNodes[0].Role);
        Assert.Equal(FleetNodeState.COMPLETED, vm.FleetNodes[0].State);
        Assert.Equal("n2", vm.FleetNodes[1].NodeId);
        Assert.Equal("coder", vm.FleetNodes[1].Role);
        Assert.Equal(FleetNodeState.RUNNING, vm.FleetNodes[1].State);

        Assert.Single(vm.Artifacts);
        Assert.Equal("art_1", vm.Artifacts[0].ArtifactId);
    }
}
