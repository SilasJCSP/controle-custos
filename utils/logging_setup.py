from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_DIR


class _ModulePrefixFilter(logging.Filter):
    def __init__(self, prefixes: tuple[str, ...]):
        super().__init__()
        self.prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith(self.prefixes)


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    app_handler = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(LOG_DIR / "erros.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)

    import_handler = RotatingFileHandler(LOG_DIR / "importacoes.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    import_handler.setLevel(logging.INFO)
    import_handler.setFormatter(formatter)
    import_handler.addFilter(
        _ModulePrefixFilter(("pipeline", "data_source", "parser", "validators", "categorias", "utils"))
    )

    root.addHandler(console_handler)
    root.addHandler(app_handler)
    root.addHandler(error_handler)
    root.addHandler(import_handler)