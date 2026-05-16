from __future__ import annotations

import logging

from app.services.email_import_service import importar_faturas_automaticamente
from pipeline.processor import run_pipeline


logger = logging.getLogger(__name__)


def sincronizar_tudo(remetente_contendo: str = "", assunto_contendo: str = "", ano_referencia: int | None = None) -> dict[str, object]:
    anexos = importar_faturas_automaticamente(remetente_contendo=remetente_contendo, assunto_contendo=assunto_contendo)
    run_pipeline(ano_referencia=ano_referencia)
    logger.info("Sincronização concluída com %d anexo(s) Gmail.", len(anexos))
    return {"gmail_anexos": len(anexos), "status": "ok"}