"""NEXORA Domain Exceptions."""


class NexoraException(Exception):
    """Base class for all application domain exceptions."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500, details: dict | list | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class InferenceBusyException(NexoraException):
    """Raised when GPU inference capacity is fully saturated."""

    def __init__(self, message: str = "Inference capacity busy. Try again shortly.", details: dict | list | None = None):
        super().__init__(message=message, code="INFERENCE_BUSY", status_code=503, details=details)


class OllamaUnavailableException(NexoraException):
    """Raised when the local Ollama daemon cannot be reached."""

    def __init__(self, message: str = "Local Ollama service is unreachable at configured URL.", details: dict | list | None = None):
        super().__init__(message=message, code="OLLAMA_UNAVAILABLE", status_code=503, details=details)


class ModelNotFoundException(NexoraException):
    """Raised when the requested model is not installed in Ollama."""

    def __init__(self, model_name: str, details: dict | list | None = None):
        message = f"Model '{model_name}' is not installed in local Ollama."
        super().__init__(message=message, code="MODEL_NOT_FOUND", status_code=404, details=details)


class InferenceTimeoutException(NexoraException):
    """Raised when Ollama inference execution exceeds the configured timeout."""

    def __init__(self, timeout_seconds: float, details: dict | list | None = None):
        message = f"Model inference timed out after {timeout_seconds}s."
        super().__init__(message=message, code="INFERENCE_TIMEOUT", status_code=504, details=details)


class OllamaMalformedResponseException(NexoraException):
    """Raised when Ollama returns an unexpected or invalid response body."""

    def __init__(self, message: str = "Ollama returned an unexpected or malformed response.", details: dict | list | None = None):
        super().__init__(message=message, code="OLLAMA_MALFORMED_RESPONSE", status_code=502, details=details)


class InvalidStateTransitionException(NexoraException):
    """Raised when an illegal task lifecycle state transition is attempted."""

    def __init__(self, current_state: str, target_state: str, task_id: str):
        message = f"Invalid state transition for task '{task_id}': cannot transition from {current_state} to {target_state}."
        super().__init__(message=message, code="INVALID_STATE_TRANSITION", status_code=409, details={"task_id": task_id, "current_state": current_state, "target_state": target_state})


class TaskNotFoundException(NexoraException):
    """Raised when a requested task does not exist."""

    def __init__(self, task_id: str):
        message = f"Task '{task_id}' not found."
        super().__init__(message=message, code="TASK_NOT_FOUND", status_code=404, details={"task_id": task_id})


class TaskRunnerBusyException(NexoraException):
    """Raised when another task is already executing."""

    def __init__(self, message: str = "Task runner capacity busy (limit: 1 active task). Try again later."):
        super().__init__(message=message, code="TASK_RUNNER_BUSY", status_code=503)


class PlanValidationException(NexoraException):
    """Raised when a generated plan fails validation."""

    def __init__(self, message: str, details: dict | list | None = None):
        super().__init__(message=message, code="PLAN_VALIDATION_ERROR", status_code=422, details=details)


class ApprovalInvalidatedException(NexoraException):
    """Raised when an approval token cannot authorize execution (expired, mismatched hash, or invalid)."""

    def __init__(self, message: str, details: dict | list | None = None):
        super().__init__(message=message, code="APPROVAL_INVALIDATED", status_code=409, details=details)

