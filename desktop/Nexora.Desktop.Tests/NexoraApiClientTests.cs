using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Nexora.Desktop.Models;
using Nexora.Desktop.Services;
using Xunit;

namespace Nexora.Desktop.Tests;

public class NexoraApiClientTests
{
    private class MockHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _handler;

        public MockHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            return Task.FromResult(_handler(request));
        }
    }

    [Fact]
    public async Task GetHealthAsync_ReturnsParsedHealth()
    {
        var handler = new MockHttpMessageHandler(req =>
        {
            Assert.Equal(HttpMethod.Get, req.Method);
            Assert.Equal("/api/health", req.RequestUri?.AbsolutePath);
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("{\"status\":\"ok\",\"version\":\"0.1.0\",\"ollama_configured\":true}")
            };
        });

        var client = new NexoraApiClient(new HttpClient(handler));
        var health = await client.GetHealthAsync();

        Assert.Equal("ok", health.Status);
        Assert.Equal("0.1.0", health.Version);
        Assert.True(health.OllamaConfigured);
    }

    [Fact]
    public async Task CreateTaskAsync_SendsRequestAndReturnsTask()
    {
        var handler = new MockHttpMessageHandler(req =>
        {
            Assert.Equal(HttpMethod.Post, req.Method);
            Assert.Equal("/api/agent/tasks", req.RequestUri?.AbsolutePath);

            var responseJson = JsonSerializer.Serialize(new TaskResponse(
                Task: new AgentTask(
                    TaskId: "task_123",
                    Prompt: "Build app",
                    Status: Models.TaskStatus.SUBMITTED
                )
            ));

            return new HttpResponseMessage(HttpStatusCode.Created)
            {
                Content = new StringContent(responseJson)
            };
        });

        var client = new NexoraApiClient(new HttpClient(handler));
        var task = await client.CreateTaskAsync("Build app", "coding-planner");

        Assert.Equal("task_123", task.TaskId);
        Assert.Equal("Build app", task.Prompt);
        Assert.Equal(Models.TaskStatus.SUBMITTED, task.Status);
    }

    [Fact]
    public async Task ListTasksAsync_ParsesBackendArrayResponse()
    {
        var handler = new MockHttpMessageHandler(req =>
        {
            Assert.Equal(HttpMethod.Get, req.Method);
            Assert.Equal("/api/agent/tasks", req.RequestUri?.AbsolutePath);
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("[{\"task_id\":\"task_123\",\"prompt\":\"Build app\",\"status\":\"SUBMITTED\"}]")
            };
        });

        var client = new NexoraApiClient(new HttpClient(handler));
        var tasks = await client.ListTasksAsync();

        var task = Assert.Single(tasks);
        Assert.Equal("task_123", task.TaskId);
    }

    [Fact]
    public async Task DecideApprovalAsync_SendsExactApprovalPayload()
    {
        var handler = new MockHttpMessageHandler(req =>
        {
            Assert.Equal(HttpMethod.Post, req.Method);
            Assert.Equal("/api/agent/tasks/task_abc/approve", req.RequestUri?.AbsolutePath);

            var responseJson = JsonSerializer.Serialize(new TaskResponse(
                Task: new AgentTask(
                    TaskId: "task_abc",
                    Prompt: "Delete temp file",
                    Status: Models.TaskStatus.EXECUTING
                )
            ));

            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(responseJson)
            };
        });

        var client = new NexoraApiClient(new HttpClient(handler));
        var updated = await client.DecideApprovalAsync("task_abc", "appr_999", approved: true);

        Assert.Equal("task_abc", updated.TaskId);
        Assert.Equal(Models.TaskStatus.EXECUTING, updated.Status);
    }

    [Fact]
    public async Task ApiError_ThrowsNexoraApiException()
    {
        var handler = new MockHttpMessageHandler(req =>
        {
            var errorPayload = "{\"error\":{\"code\":\"MODEL_NOT_FOUND\",\"message\":\"Model not found\",\"details\":null}}";
            return new HttpResponseMessage(HttpStatusCode.NotFound)
            {
                Content = new StringContent(errorPayload)
            };
        });

        var client = new NexoraApiClient(new HttpClient(handler));
        var ex = await Assert.ThrowsAsync<NexoraApiException>(() => client.GetTaskAsync("task_missing"));

        Assert.Equal("MODEL_NOT_FOUND", ex.Code);
        Assert.Equal("Model not found", ex.Message);
        Assert.Equal(404, ex.StatusCode);
    }
}
