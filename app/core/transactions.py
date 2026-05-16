from __future__ import annotations

import hashlib

import pandas as pd

from utils.text import normalizar_descricao


def gerar_id_transacao(row) -> str:
    data = row.get("data", "") if hasattr(row, "get") else ""
    descricao = row.get("descricao", "") if hasattr(row, "get") else ""
    valor = row.get("valor", "") if hasattr(row, "get") else ""

    data_normalizada = pd.to_datetime(data, errors="coerce")
    data_texto = "" if pd.isna(data_normalizada) else data_normalizada.date().isoformat()

    try:
        valor_texto = f"{float(valor):.2f}"
    except Exception:
        valor_texto = str(valor).strip()

    base = "|".join([data_texto, normalizar_descricao(str(descricao)), valor_texto])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def deduplicar_transacoes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    resultado = df.copy()
    if "id_transacao" not in resultado.columns:
        resultado["id_transacao"] = resultado.apply(gerar_id_transacao, axis=1)

    return resultado.drop_duplicates(subset=["id_transacao"], keep="first").reset_index(drop=True)