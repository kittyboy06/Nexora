import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from backend.app.core.config import Settings


def setup_logging(settings: Settings) -> logging.Logger:
    """Configure structured logging with console and rotating file sinks."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on re-initialization
    if not root_logger.handlers:
        # Console Sink
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(log_format)
        root_logger.addHandler(console_handler)

        # File Sink
        log_file = settings.get_log_file_path()
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(log_format)
            root_logger.addHandler(file_handler)
        except OSError as e:
            # Fallback if file logging fails (e.g. read-only filesystem)
            root_logger.warning("Could not initialize file log handler at %s: %s", log_file, e)

    # Suppress overly verbose loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger("nexora")
    logger.info("Structured logging initialized (level=%s)", settings.LOG_LEVEL)
    return logger
