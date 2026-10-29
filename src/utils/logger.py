"""Sistema de logging interno para diagnóstico e depuração."""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Diretório de logs dentro do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "nexus_debug.log")

_logger = logging.getLogger("NexusFetch")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    # Arquivo rotativo de log de no máximo 5MB
    handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)

def log_info(msg: str):
    _logger.info(msg)

def log_warning(msg: str):
    _logger.warning(msg)

def log_error(msg: str, exc: Exception = None):
    if exc:
        _logger.error(f"{msg}: {exc}", exc_info=True)
    else:
        _logger.error(msg)

def log_debug(msg: str):
    _logger.debug(msg)
