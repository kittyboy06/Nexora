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
