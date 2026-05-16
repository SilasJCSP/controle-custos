from __future__ import annotations

import hashlib
import logging
from typing import Iterable

import pandas as pd

from utils.text import normalizar_descricao


logger = logging.getLogger(__name__)
COLUNAS_PADRAO = ["data", "descricao", "valor", "categoria"]


def gerar_id_transacao(row) -> str:
    data = row.get("data", "") if hasattr(row, "get") else ""
    descricao = row.get("descricao", "") if hasattr(row, "get") else ""
    valor = row.get("valor", "") if hasattr(row, "get") else ""

    data_normalizada = pd.to_datetime(data, errors="coerce")
    if pd.isna(data_normalizada):
        data_texto = ""
    else:
        data_texto = data_normalizada.date().isoformat()

    try:
        valor_texto = f"{float(valor):.2f}"
    except Exception:
        valor_texto = str(valor).strip()

    base = "|".join([data_texto, normalizar_descricao(str(descricao)), valor_texto])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def validar_colunas_obrigatorias(df: pd.DataFrame, colunas_obrigatorias: Iterable[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    colunas = list(colunas_obrigatorias or COLUNAS_PADRAO)
    resultado = df.copy()
    faltantes = [col for col in colunas if col not in resultado.columns]
    if faltantes:
        logger.warning("Colunas obrigatórias ausentes: %s", ", ".join(faltantes))
        for coluna in faltantes:
            resultado[coluna] = pd.NA
    return resultado


def validar_datas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "data" not in df.columns:
        return df.copy()

    resultado = df.copy()
    resultado["data"] = pd.to_datetime(resultado["data"], errors="coerce")
    invalidas = resultado["data"].isna()
    if invalidas.any():
        logger.warning("Registros descartados por data inválida: %d", int(invalidas.sum()))
        resultado = resultado.loc[~invalidas].copy()
    return resultado


def validar_valores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "valor" not in df.columns:
        return df.copy()

    resultado = df.copy()
    resultado["valor"] = pd.to_numeric(resultado["valor"], errors="coerce")
    invalidos = resultado["valor"].isna()
    if invalidos.any():
        logger.warning("Registros descartados por valor inválido: %d", int(invalidos.sum()))
        resultado = resultado.loc[~invalidos].copy()
    return resultado


def validar_duplicidade(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    resultado = df.copy()
    if "id_transacao" not in resultado.columns:
        resultado["id_transacao"] = resultado.apply(gerar_id_transacao, axis=1)
    else:
        mascara_vazia = resultado["id_transacao"].astype(str).str.strip().isin(["", "nan", "None"])
        if mascara_vazia.any():
            resultado.loc[mascara_vazia, "id_transacao"] = resultado.loc[mascara_vazia].apply(gerar_id_transacao, axis=1)

    antes = len(resultado)
    resultado = resultado.drop_duplicates(subset=["id_transacao"], keep="first").copy()
    removidos = antes - len(resultado)
    if removidos:
        logger.info("Duplicidades removidas: %d", removidos)
    return resultado


def validar_schema_dataframe(df: pd.DataFrame, colunas_obrigatorias: Iterable[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(colunas_obrigatorias or COLUNAS_PADRAO) + ["id_transacao"])

    resultado = validar_colunas_obrigatorias(df, colunas_obrigatorias)

    if "descricao" in resultado.columns:
        resultado["descricao"] = resultado["descricao"].astype(str).str.strip()
        vazias = resultado["descricao"].isin(["", "nan", "None"])
        if vazias.any():
            logger.warning("Registros descartados por descrição vazia: %d", int(vazias.sum()))
            resultado = resultado.loc[~vazias].copy()

    if "categoria" in resultado.columns:
        resultado["categoria"] = resultado["categoria"].astype(str).str.strip().replace({"nan": "", "None": ""})
        faltantes = resultado["categoria"].isin(["", "nan", "None"])
        if faltantes.any():
            logger.info("Categorias vazias ajustadas para 'Outros': %d", int(faltantes.sum()))
            resultado.loc[faltantes, "categoria"] = "Outros"

    resultado = validar_datas(resultado)
    resultado = validar_valores(resultado)
    resultado = validar_duplicidade(resultado)

    if "categoria" in resultado.columns:
        resultado["categoria"] = resultado["categoria"].astype(str).str.strip().replace({"": "Outros", "nan": "Outros", "None": "Outros"})

    return resultado.reset_index(drop=True)