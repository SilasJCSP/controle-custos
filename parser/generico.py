from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from parser.base import ParseContext, extrair_texto_pdf, extrair_transacoes_basicas, normalizar_dataframe_parsado, tentar_ocr_mock


logger = logging.getLogger(__name__)


def parse(caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
    logger.info("Parser genérico para: %s", caminho_pdf.name)
    if not caminho_pdf.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

    try:
        texto = extrair_texto_pdf(caminho_pdf)
    except Exception as exc:
        logger.warning("Falha ao extrair texto direto de %s: %s", caminho_pdf.name, exc)
        texto = tentar_ocr_mock(caminho_pdf)

    linhas = texto.splitlines()
    contexto = ParseContext(arquivo_fatura=caminho_pdf.name, banco="generico", ano_referencia=ano_referencia)
    df = extrair_transacoes_basicas(linhas, contexto)
    df = normalizar_dataframe_parsado(df, banco="generico", arquivo_fatura=caminho_pdf.name)
    return df.reset_index(drop=True)
