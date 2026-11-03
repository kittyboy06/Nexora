# NEXORA — PHASE 2 DESIGN
## Hybrid Autonomous Agent Engine

Phase 1 of NEXORA has been completed and verified.

Your next responsibility is to design Phase 2: the Hybrid Agent Engine.

## 1. Architectural Decision

Use a HYBRID PLANNING ARCHITECTURE.

The local LLM (Ollama + qwen3.5:9b) is responsible for:
- Understanding user objectives.
- Generating structured task plans.
- Selecting appropriate registered tools.
- Evaluating execution results.
- Suggesting recovery strategies.

Python is responsible for:
- Validating plans.
- Enforcing execution limits.
- Checking permissions.
- Managing task states.
- Executing tools.
- Handling retries.
- Verifying execution constraints.

The LLM must never directly execute arbitrary code or bypass the Python execution layer.

## 2. Required Components

Design the following modules:

1. Agent Orchestrator
2. Task Parser
3. Planning Engine
4. Plan Validator
5. Tool Registry
6. Execution Engine
7. Permission Manager
8. Result Evaluator
9. Agent State Manager

Clearly define the responsibility and interface of each module.

## 3. Structured Plan

Design Pydantic models for:

- AgentTask
- TaskPlan
- PlanStep
- ToolCall
- ExecutionResult
- StepResult
- TaskStatus
- StepStatus
- PermissionDecision

Plans must use structured JSON.

Define validation rules for:
- Required fields.
- Unique step IDs.
- Registered tool names.
- Tool argument validation.
- Maximum plan steps.
- Valid dependencies.
- Risk classifications.
- Invalid or malformed model responses.

Never execute an unvalidated plan.

## 4. Execution Limits

Introduce configurable execution limits with these initial defaults:

- Maximum plan steps: 10.
- Maximum execution iterations: 15.
- Maximum retries per step: 2.
- Maximum concurrent tasks: 1.
- Maximum concurrent LLM generations: 1.
- Maximum planning attempts: 2.
- Maximum execution duration: 300 seconds.
- Initial context target: 4096 tokens.

All limits must be enforced by Python.

## 5. Permission System

Design three permission levels:

SAFE:
Can execute automatically.

CONTROLLED:
Requires approval according to configured policy.

SENSITIVE:
Always requires explicit user approval.

Permission validation must happen before every tool execution, including retries.

Do not implement unrestricted shell access or actual computer control.

## 6. Initial Tool Strategy

Use mock tools only.

Create examples such as:

- mock_search
- mock_summarize
- mock_calculate
- mock_file_read

These tools must simulate operations without accessing or modifying real user data.

Design the Tool Registry so real tools can be registered in future phases.

## 7. Execution Workflow

Implement the design around this lifecycle:

USER REQUEST
→ TASK PARSING
→ LLM PLANNING
→ PLAN VALIDATION
→ PERMISSION CHECK
→ TOOL EXECUTION
→ RESULT EVALUATION
→ NEXT STEP OR RECOVERY
→ FINAL RESPONSE

Define the behaviour for:
- Successful execution.
- Tool failures.
- Invalid model plans.
- Permission denial.
- Execution timeouts.
- Retry exhaustion.
- Cancellation.

## 8. Integration with Phase 1

Reuse the existing:
- FastAPI application.
- Ollama service.
- Configuration system.
- Logging system.
- Concurrency guard.
- Error handling conventions.

Do not unnecessarily rewrite Phase 1.

## 9. Testing Strategy

Design tests for:

- Valid LLM-generated plans.
- Invalid plans.
- Unknown tools.
- Malformed tool arguments.
- Permission denial.
- Successful execution.
- Tool failure.
- Retry handling.
- Execution limits.
- Cancellation.
- Multi-step task completion.

Use mocked LLM responses and mock tools.

Tests must not require real desktop interaction.

## 10. Deliverables

Before implementing code, produce:

1. Phase 2 Design Specification.
2. Updated project directory structure.
3. Component responsibility definitions.
4. Data models and schemas.
5. Execution workflow.
6. Permission and security design.
7. Error-handling strategy.
8. Testing strategy.
9. Implementation plan divided into manageable milestones.

Do not begin implementation until the design has been reviewed.

Do not implement frontend, browser automation, desktop automation, persistent memory or background scheduling.

Maintain all Phase 1 functionality.