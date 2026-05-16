from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from parser.base import ParseContext, extrair_texto_pdf, extrair_transacoes_basicas, normalizar_dataframe_parsado, tentar_ocr_mock


logger = logging.getLogger(__name__)

RUIDOS_MERCADO_PAGO = (
    "saldo",
    "limite",
    "fatura",
    "total pago",
    "pagamento da fatura",
    "parcelas",
)


def _filtrar_ruidos(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    desc = df["descricao"].astype(str).str.lower()
    mascara = pd.Series(True, index=df.index)
    for ruído in RUIDOS_MERCADO_PAGO:
        mascara &= ~desc.str.contains(ruído, regex=False)
    return df.loc[mascara].copy()


def parse(caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
    if not caminho_pdf.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

    try:
        texto = extrair_texto_pdf(caminho_pdf)
    except Exception as exc:
        logger.warning("Falha ao extrair texto direto de %s: %s", caminho_pdf.name, exc)
        texto = tentar_ocr_mock(caminho_pdf)

    linhas = texto.splitlines()
    contexto = ParseContext(arquivo_fatura=caminho_pdf.name, banco="mercado_pago", ano_referencia=ano_referencia)
    df = extrair_transacoes_basicas(linhas, contexto)
    df = normalizar_dataframe_parsado(df, banco="mercado_pago", arquivo_fatura=caminho_pdf.name)
    df = _filtrar_ruidos(df)

    if df.empty:
        logger.info("Nenhuma transação Mercado Pago encontrada em %s", caminho_pdf.name)
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    return df.reset_index(drop=True)
