from __future__ import annotations

import pandas as pd

from app.services.insights_service import comparar_meses, detectar_recorrentes, gerar_insights, prever_fechamento, resumo_mensal


def _df_base():
    return pd.DataFrame(
        [
            {"data": "2026-04-01", "descricao": "Netflix", "valor": 39.9, "categoria": "Serviços"},
            {"data": "2026-04-10", "descricao": "Uber", "valor": 25.0, "categoria": "Transporte"},
            {"data": "2026-05-01", "descricao": "Netflix", "valor": 39.9, "categoria": "Serviços"},
            {"data": "2026-05-03", "descricao": "Ifood", "valor": 50.0, "categoria": "Alimentação"},
        ]
    )


def test_resumo_e_comparacao():
    df = _df_base()
    resumo = resumo_mensal(df)
    comp = comparar_meses(df)
    previsao = prever_fechamento(df)

    assert len(resumo) == 2
    assert "variacao_percentual" in comp
    assert "previsao" in previsao


def test_recorrentes_e_insights():
    df = _df_base()
    recorrentes = detectar_recorrentes(df)
    insights = gerar_insights(df)

    assert not recorrentes.empty
    assert isinstance(insights, list)