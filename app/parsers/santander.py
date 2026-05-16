from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.parsers.base import BaseParser
from app.core.parsing import normalizar_dataframe_parsado

try:
    from leitor_pdf_santander import extrair_transacoes_santander
except Exception:
    extrair_transacoes_santander = None


class SantanderParser(BaseParser):
    banco = "santander"

    def parse(self, caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        if not caminho_pdf.exists():
            raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

        if extrair_transacoes_santander is None:
            return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

        df = extrair_transacoes_santander(caminho_pdf, ano_referencia=ano_referencia or pd.Timestamp.today().year)
        if df.empty:
            return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])
        return normalizar_dataframe_parsado(df, banco=self.banco, arquivo_fatura=caminho_pdf.name)

    def parse_text(self, texto: str, arquivo: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        return self.parse(arquivo, ano_referencia=ano_referencia)