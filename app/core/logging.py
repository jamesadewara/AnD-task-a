import sys
import contextvars
from loguru import logger
from app.core.config import settings

# Context variable to hold the reasoning steps for the current request
# This ensures that logs are only captured for the specific client that made the request.
reasoning_ctx = contextvars.ContextVar("reasoning_ctx", default=None)

def reasoning_sink(message):
    """
    Sink that captures loguru messages and appends them to the current 
    request's reasoning chain if reasoning_ctx is active.
    """
    ctx = reasoning_ctx.get()
    if ctx is not None and isinstance(ctx, list):
        record = message.record
        # Format the log as a reasoning step
        step = {
            "step": "internal_log",
            "action": f"{record['name']}:{record['function']}",
            "output": record["message"]
        }
        ctx.append(step)

def setup_logging():
    """
    Centralized logging configuration for AnD AI.
    Outputs to terminal (stdout) ONLY if settings.DEBUG is True.
    """
    # Remove all existing handlers
    logger.remove()

    if settings.DEBUG:
        # Configure loguru for terminal output
        import io
        safe_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        logger.add(
            safe_stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        logger.info("Terminal logging initialized (DEBUG=True) via Loguru")
    else:
        # In production (non-DEBUG), we might want to log only ERROR/CRITICAL
        # but the user requested "if the DEBUG is true logging shows else it does not"
        pass

    # Add the reasoning sink (always active, but only captures if context is set)
    logger.add(reasoning_sink, level="INFO", colorize=False)
