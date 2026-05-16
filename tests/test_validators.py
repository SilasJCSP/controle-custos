from __future__ import annotations

import pandas as pd

from validators.dataframe_validator import validar_schema_dataframe


def test_validar_schema_remove_invalidos_e_duplicados():
    df = pd.DataFrame(
        [
            {"data": "2026-05-01", "descricao": "Uber", "valor": 42.5, "categoria": "Transporte"},
            {"data": "2026-05-01", "descricao": "Uber", "valor": 42.5, "categoria": "Transporte"},
            {"data": "invalid", "descricao": "X", "valor": 1, "categoria": "Outros"},
            {"data": "2026-05-02", "descricao": "", "valor": 1, "categoria": "Outros"},
        ]
    )

    resultado = validar_schema_dataframe(df)

    assert len(resultado) == 1
    assert "id_transacao" in resultado.columns
    assert resultado.iloc[0]["descricao"] == "Uber"