from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.parsers.base import BaseParser, parse_texto_generico
from app.core.parsing import extrair_texto_pdf, tentar_ocr_mock


class NubankParser(BaseParser):
    banco = "nubank"

    def parse(self, caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        texto = ""
        try:
            texto = extrair_texto_pdf(caminho_pdf)
        except Exception:
            texto = tentar_ocr_mock(caminho_pdf)
        return self.parse_text(texto, caminho_pdf, ano_referencia=ano_referencia)

    def parse_text(self, texto: str, arquivo: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        return parse_texto_generico(texto, arquivo, self.banco, ano_referencia=ano_referencia)