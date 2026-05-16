from __future__ import annotations

import calendar
from datetime import date

import pandas as pd


def resumo_mensal(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["mes", "total", "qtd"])
    base = df.copy()
    base["mes"] = pd.to_datetime(base["data"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    base = base.dropna(subset=["mes", "valor"])
    resumo = base.groupby("mes", as_index=False).agg(total=("valor", "sum"), qtd=("valor", "size"))
    return resumo.sort_values("mes")


def comparar_meses(df: pd.DataFrame) -> dict[str, object]:
    resumo = resumo_mensal(df)
    if len(resumo) < 2:
        return {"mensagem": "Dados insuficientes para comparação."}

    atual = resumo.iloc[-1]
    anterior = resumo.iloc[-2]
    total_anterior = float(anterior["total"])
    variacao = ((float(atual["total"]) - total_anterior) / total_anterior) * 100 if total_anterior else 0.0
    return {
        "mes_atual": str(atual["mes"])[:7],
        "mes_anterior": str(anterior["mes"])[:7],
        "total_atual": float(atual["total"]),
        "total_anterior": total_anterior,
        "variacao_percentual": round(variacao, 2),
    }


def prever_fechamento(df: pd.DataFrame) -> dict[str, object]:
    resumo = resumo_mensal(df)
    today = date.today()
    dias_mes = calendar.monthrange(today.year, today.month)[1]
    dias_passados = today.day
    dias_restantes = max(0, dias_mes - dias_passados)

    if resumo.empty:
        return {"previsao": 0, "gasto_diario_medio": 0, "dias_restantes": dias_restantes, "confianca": 0.0}

    base_mes = pd.to_datetime(df["data"], errors="coerce")
    base_mes = df.loc[base_mes.dt.year.eq(today.year) & base_mes.dt.month.eq(today.month)].copy()
    if base_mes.empty:
        return {"previsao": 0, "gasto_diario_medio": 0, "dias_restantes": dias_restantes, "confianca": 0.0}

    total_atual = float(base_mes["valor"].sum())
    gasto_diario = total_atual / max(1, dias_passados)
    previsao = total_atual + (gasto_diario * dias_restantes)

    confianca = 0.85
    if dias_passados < 5:
        confianca = 0.45
    elif dias_passados < 10:
        confianca = 0.65

    return {
        "previsao": round(previsao, 2),
        "gasto_diario_medio": round(gasto_diario, 2),
        "dias_restantes": int(dias_restantes),
        "confianca": round(confianca, 2),
    }


def detectar_recorrentes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["descricao", "ocorrencias", "media"])
    base = df.copy()
    base["descricao_norm"] = base["descricao"].astype(str).str.lower().str.strip()
    recorrentes = (
        base.groupby("descricao_norm", as_index=False)
        .agg(ocorrencias=("descricao_norm", "size"), media=("valor", "mean"), descricao=("descricao", "first"))
        .query("ocorrencias >= 2")
        .sort_values(["ocorrencias", "media"], ascending=[False, False])
    )
    return recorrentes[["descricao", "ocorrencias", "media"]]


def top_despesas(df: pd.DataFrame, limite: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["descricao", "valor"])
    return df.groupby("descricao", as_index=False)["valor"].sum().sort_values("valor", ascending=False).head(limite)


def gerar_insights(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["Sem dados suficientes para gerar insights."]

    insights: list[str] = []
    comparacao = comparar_meses(df)
    variacao = comparacao.get("variacao_percentual")
    if isinstance(variacao, (int, float)):
        if variacao > 0:
            insights.append(f"Seus gastos aumentaram {variacao}% em relação ao mês anterior.")
        elif variacao < 0:
            insights.append(f"Seus gastos caíram {abs(variacao)}% em relação ao mês anterior.")

    por_categoria = df.groupby("categoria", as_index=False)["valor"].sum().sort_values("valor", ascending=False)
    if not por_categoria.empty:
        insights.append(f"Categoria dominante: {por_categoria.iloc[0]['categoria']}.")

    recorrentes = detectar_recorrentes(df)
    if not recorrentes.empty:
        insights.append(f"{len(recorrentes)} gastos recorrentes detectados, incluindo {recorrentes.iloc[0]['descricao']}.")

    previsao = prever_fechamento(df)
    if previsao.get("previsao", 0):
        insights.append(f"Previsão de fechamento do mês: R$ {float(previsao['previsao']):.2f}.")

    return insights[:5]