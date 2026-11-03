"""Live end-to-end verification script for Phase 3 with local Ollama qwen3.5:9b."""

import asyncio
import json
import sys
import httpx
from httpx import ASGITransport

from backend.app.main import create_app
from backend.app.models.agent import TaskStatus


async def main():
    print("Initializing NEXORA live engine...")
    app = create_app()

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            # 1. Health & Ollama check
            health_res = await client.get("/api/health")
            print("Health Check:", health_res.status_code, health_res.json())

            ollama_res = await client.get("/api/ollama/status")
            print("Ollama Status:", ollama_res.status_code, ollama_res.json())

            # 2. Submit Real Phase 3 Task
            prompt = "Create a file named welcome.txt in the workspace with content 'Hello from NEXORA Phase 3', and then read it back."
            print(f"\nSubmitting task: {prompt}")
            task_res = await client.post("/api/agent/tasks", json={"prompt": prompt})
            print("Task Submission HTTP:", task_res.status_code)
            if task_res.status_code != 201:
                print("Failed to submit task:", task_res.text)
                return

            task_id = task_res.json()["task"]["task_id"]
            print(f"Task ID: {task_id}")

            # 3. Poll Task Execution
            print("Waiting for Ollama qwen3.5:9b to plan and execute...")
            for i in range(120):
                await asyncio.sleep(2.0)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task = get_res.json()["task"]
                status = task["status"]
                print(f"[{i*2}s] Status: {status} (Iterations: {task['iterations_used']})")

                if status == TaskStatus.WAITING_APPROVAL:
                    appr = task["pending_approval"]
                    print(f"Task paused for approval on tool: {appr['tool_name']}. Auto-approving for live test...")
                    appr_res = await client.post(
                        f"/api/agent/tasks/{task_id}/approve",
                        json={"approval_id": appr["approval_id"], "approved": True},
                    )
                    print("Approval response:", appr_res.status_code)

                if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    print(f"\nTask reached terminal state: {status}")
                    print("\nGenerated Plan:")
                    if task.get("plan"):
                        for step in task["plan"]["steps"]:
                            print(f"  Step {step['step_id']}: {step['tool_call']['tool_name']}({step['tool_call']['arguments']})")

                    print("\nExecution Trace:")
                    for res in task.get("execution_trace", []):
                        print(f"  Step {res['step_id']} [{res['tool_name']}]: status={res['status']} in {res['duration_ms']}ms")
                        print(f"    Output: {res['output']}")

                    if status == TaskStatus.COMPLETED:
                        print("\nSUCCESS! Phase 3 live hardware task completed successfully!")
                    else:
                        print("\nTask failed with error:", task.get("error_message"))
                    return

            print("Timed out waiting for task completion.")


if __name__ == "__main__":
    asyncio.run(main())
