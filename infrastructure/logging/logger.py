"""Configuração de logs (arquivo rotativo + console)."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_TAG = "_nexus_handler"


def setup_logging(log_dir: Path, level: str = "INFO") -> Path:
    """Configura o logger 'nexus'. Idempotente. Devolve o caminho do arquivo de log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nexus")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in [h for h in logger.handlers if getattr(h, _TAG, False)]:
        logger.removeHandler(h)
        h.close()
    file = log_dir / "nexus.log"
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ]
    for h in handlers:
        h.setFormatter(logging.Formatter(FORMAT))
        setattr(h, _TAG, True)
        logger.addHandler(h)
    logger.propagate = False
    return file
