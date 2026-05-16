from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.parsing import ParseContext, extrair_texto_pdf, extrair_transacoes_basicas, normalizar_dataframe_parsado, tentar_ocr_mock
from app.parsers.base import BaseParser


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
    descricao = df["descricao"].astype(str).str.lower()
    mascara = pd.Series(True, index=df.index)
    for ruido in RUIDOS_MERCADO_PAGO:
        mascara &= ~descricao.str.contains(ruido, regex=False)
    return df.loc[mascara].copy()


class MercadoPagoParser(BaseParser):
    banco = "mercado_pago"

    def parse(self, caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        if not caminho_pdf.exists():
            raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

        try:
            texto = extrair_texto_pdf(caminho_pdf)
        except Exception:
            texto = tentar_ocr_mock(caminho_pdf)

        return self.parse_text(texto, caminho_pdf, ano_referencia=ano_referencia)

    def parse_text(self, texto: str, arquivo: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        contexto = ParseContext(arquivo_fatura=arquivo.name, banco=self.banco, ano_referencia=ano_referencia)
        df = extrair_transacoes_basicas(texto.splitlines(), contexto)
        df = normalizar_dataframe_parsado(df, banco=self.banco, arquivo_fatura=arquivo.name)
        df = _filtrar_ruidos(df)

        if df.empty:
            return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

        return df.reset_index(drop=True)


def parse(caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
    return MercadoPagoParser().parse(caminho_pdf, ano_referencia=ano_referencia)