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


class PathTraversalException(NexoraException):
    """Raised when a path escapes the designated workspace sandbox."""

    def __init__(self, message: str = "Access denied: Path escapes workspace jail.", details: dict | list | None = None):
        super().__init__(message=message, code="PATH_TRAVERSAL_DENIED", status_code=403, details=details)


class FileTooLargeException(NexoraException):
    """Raised when a file exceeds the allowed size limit."""

    def __init__(self, message: str = "File size exceeds allowed limit.", details: dict | list | None = None):
        super().__init__(message=message, code="FILE_TOO_LARGE", status_code=413, details=details)


class FileAlreadyExistsException(NexoraException):
    """Raised when a file creation/copy/move would overwrite an existing file without permission."""

    def __init__(self, message: str = "File already exists and overwrite was not permitted.", details: dict | list | None = None):
        super().__init__(message=message, code="FILE_ALREADY_EXISTS", status_code=409, details=details)


class AppNotFoundException(NexoraException):
    """Raised when an application executable cannot be located or verified."""

    def __init__(self, message: str = "Application not found or executable path invalid.", details: dict | list | None = None):
        super().__init__(message=message, code="APP_NOT_FOUND", status_code=404, details=details)


class SystemProcessProtectedException(NexoraException):
    """Raised when an action attempts to terminate or modify a protected Windows system process."""

    def __init__(self, message: str = "Access denied: Cannot manipulate protected system process.", details: dict | list | None = None):
        super().__init__(message=message, code="SYSTEM_PROCESS_PROTECTED", status_code=403, details=details)


class ProcessNotFoundException(NexoraException):
    """Raised when a process with the specified PID is not running."""

    def __init__(self, message: str = "Process PID not found or already terminated.", details: dict | list | None = None):
        super().__init__(message=message, code="PROCESS_NOT_FOUND", status_code=404, details=details)


class CommandNotAllowedException(NexoraException):
    """Raised when a terminal command is not in the configured execution allowlist."""

    def __init__(self, message: str = "Command is not permitted by terminal allowlist policy.", details: dict | list | None = None):
        super().__init__(message=message, code="COMMAND_NOT_ALLOWED", status_code=403, details=details)


class CommandExecutionTimeoutException(NexoraException):
    """Raised when a terminal command execution exceeds the configured timeout."""

    def __init__(self, message: str = "Command execution exceeded timeout threshold.", details: dict | list | None = None):
        super().__init__(message=message, code="COMMAND_TIMEOUT", status_code=504, details=details)





class ConversationNotFoundException(NexoraException):
    """Raised when the requested conversation does not exist."""

    def __init__(self, conversation_id: str, details: dict | list | None = None):
        message = f"Conversation '{conversation_id}' was not found."
        super().__init__(message=message, code="CONVERSATION_NOT_FOUND", status_code=404, details=details)
