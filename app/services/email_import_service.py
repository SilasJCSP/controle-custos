from __future__ import annotations

import logging

from data_source.gmail import importar_faturas_gmail


logger = logging.getLogger(__name__)


def importar_faturas_automaticamente(remetente_contendo: str = "", assunto_contendo: str = ""):
    anexos = importar_faturas_gmail(remetente_contendo=remetente_contendo, assunto_contendo=assunto_contendo)
    logger.info("Importação Gmail finalizada: %d anexo(s) encontrado(s)", len(anexos))
    return anexos