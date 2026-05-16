from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.parsing import ParseContext, extrair_texto_pdf, normalizar_dataframe_parsado


def parse_texto_generico(texto: str, arquivo: Path, banco: str, ano_referencia: int | None = None) -> pd.DataFrame:
    from app.core.parsing import extrair_transacoes_basicas

    contexto = ParseContext(arquivo_fatura=arquivo.name, banco=banco, ano_referencia=ano_referencia)
    df = extrair_transacoes_basicas(texto.splitlines(), contexto)
    return normalizar_dataframe_parsado(df, banco=banco, arquivo_fatura=arquivo.name)