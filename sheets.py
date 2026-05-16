"""Funções para leitura de gastos manuais no Google Sheets."""

from __future__ import annotations

import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDENCIAIS_PATH, NOME_ABA, NOME_PLANILHA, SCOPES


COLUNAS_ESPERADAS = ["data", "descricao", "valor", "categoria"]


def ler_gastos_sheets() -> pd.DataFrame:
    """Conecta no Google Sheets e retorna os dados como DataFrame.

    Espera encontrar as colunas: data, descricao, valor, categoria.
    """
    if not CREDENCIAIS_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de credenciais não encontrado: {CREDENCIAIS_PATH}"
        )

    credenciais = ServiceAccountCredentials.from_json_keyfile_name(
        str(CREDENCIAIS_PATH), SCOPES
    )
    cliente = gspread.authorize(credenciais)

    planilha = cliente.open(NOME_PLANILHA)
    aba = planilha.worksheet(NOME_ABA) if NOME_ABA else planilha.get_worksheet(0)

    registros = aba.get_all_records()
    if not registros:
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

    df = pd.DataFrame(registros)
    # Padroniza nomes das colunas para minúsculo sem espaços extras.
    df.columns = [str(col).strip().lower() for col in df.columns]

    faltantes = [col for col in COLUNAS_ESPERADAS if col not in df.columns]
    if faltantes:
        raise ValueError(
            "A planilha não possui todas as colunas esperadas. "
            f"Faltando: {', '.join(faltantes)}"
        )

    df = df[COLUNAS_ESPERADAS].copy()

    # Conversões de tipo básicas.
    df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["descricao"] = df["descricao"].astype(str).str.strip()
    df["categoria"] = df["categoria"].astype(str).str.strip().replace("", "Outros")

    # Remove linhas inválidas essenciais.
    df = df.dropna(subset=["data", "descricao", "valor"])

    return df
