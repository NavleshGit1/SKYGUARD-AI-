import logging
import sys
import json
import time
from typing import Any, Dict
from datetime import datetime, timezone

class ConsoleColorFormatter(logging.Formatter):
    """Human-friendly colored console output for development."""
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        time_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        req_id = f" [{record.request_id}]" if hasattr(record, "request_id") else ""
        dur = f" ({record.duration_ms:.2f}ms)" if hasattr(record, "duration_ms") else ""
        # Clean non-ASCII for Windows cp1252 safety
        msg = record.getMessage().encode('ascii', 'replace').decode('ascii')
        return f"{time_str} {color}{record.levelname:<7}{self.RESET} [{record.name}]{req_id} {msg}{dur}"

def setup_logger(name: str = "skyguard", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ConsoleColorFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        
    return logger

logger = setup_logger()
