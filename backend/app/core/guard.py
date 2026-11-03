import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from backend.app.core.exceptions import InferenceBusyException

logger = logging.getLogger("nexora.guard")


class InferenceGuard:
    """Protects GPU VRAM by bounding concurrent model inference."""

    def __init__(self, limit: int = 1, timeout: float = 5.0):
        self._limit = limit
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(limit)

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def timeout(self) -> float:
        return self._timeout

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[None, None]:
        """Acquire the semaphore within the timeout window or raise InferenceBusyException."""
        logger.debug("Attempting to acquire inference lock (timeout=%.1fs)", self._timeout)
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._timeout)
        except asyncio.TimeoutError:
            logger.warning("Inference concurrency limit reached (%d). Acquisition timed out.", self._limit)
            raise InferenceBusyException(
                message=f"Inference capacity currently saturated (limit: {self._limit}). Try again shortly.",
                details={"concurrency_limit": self._limit, "timeout_seconds": self._timeout},
            )

        try:
            logger.debug("Inference lock acquired")
            yield
        finally:
            self._semaphore.release()
            logger.debug("Inference lock released")
