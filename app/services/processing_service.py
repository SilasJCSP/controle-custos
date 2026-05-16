from __future__ import annotations

import pandas as pd

from validators.dataframe_validator import validar_schema_dataframe


def preparar_transacoes(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    return validar_schema_dataframe(df, colunas)