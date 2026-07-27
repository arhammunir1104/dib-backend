# app/logging/setup.py
import logging
import sys
from app.core.config import settings

def setup_logging():
    logger = logging.getLogger("dib_ai")
    logger.setLevel(settings.LOG_LEVEL.upper())

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(settings.LOG_LEVEL.upper())
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    # Avoid propagation to root logger
    logger.propagate = False
    return logger

logger = setup_logging()