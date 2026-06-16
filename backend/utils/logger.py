"""
Loguru logger configuration.

Provides a centralized logger configuration for the entire backend.
"""

import sys
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
from config.settings import settings


def setup_logger():
    """
    Configure loguru logger with custom format and handlers.
    
    - Console output with colors for development
    - File logging for production
    - Different log levels for different modules
    """
    # Remove default handler
    logger.remove()
    
    # Console handler with colors and detailed format
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # File handler for all logs
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "backend_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="00:00",  # Rotate at midnight
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress old logs
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Thread-safe logging
    )
    
    # Error log file (only errors and above)
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",  # Keep error logs longer
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )
    
    # Set specific log levels for different modules
    logger.configure(
        handlers=[
            {
                "sink": sys.stderr,
                "level": settings.LOG_LEVEL,
                "filter": lambda record: record["level"].no >= logger.level(settings.LOG_LEVEL).no
            }
        ]
    )
    
    # Configure third-party loggers
    import logging
    
    # Intercept standard logging messages and route them to loguru
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                # Map logging levels to loguru levels
                level_map = {
                    logging.CRITICAL: "CRITICAL",
                    logging.ERROR: "ERROR",
                    logging.WARNING: "WARNING",
                    logging.INFO: "INFO",
                    logging.DEBUG: "DEBUG",
                }
                level = level_map.get(record.levelno, "INFO")

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    # Replace handlers for all loggers
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Set levels for specific loggers
    for logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "litellm",
    ]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False
    
    logger.info("Logger configured successfully")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    return logger


# Initialize logger on import
setup_logger()
