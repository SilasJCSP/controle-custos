from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from parser.base import normalizar_dataframe_parsado

try:
    from leitor_pdf_santander import extrair_transacoes_santander
except Exception:
    extrair_transacoes_santander = None


logger = logging.getLogger(__name__)


def parse(caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
    """Parser especializado para Santander."""
    if not caminho_pdf.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

    if extrair_transacoes_santander is None:
        logger.warning("Parser Santander não disponível; retornando DataFrame vazio.")
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    df = extrair_transacoes_santander(caminho_pdf, ano_referencia=ano_referencia or pd.Timestamp.today().year)
    if df.empty:
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    df = normalizar_dataframe_parsado(df, banco="santander", arquivo_fatura=caminho_pdf.name)
    return df.reset_index(drop=True)
