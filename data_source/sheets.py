from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable
import unicodedata

import pandas as pd

from categorias import normalizar_categoria
from config import (
    NOME_ABA,
    NOME_ABA_CONTROLE,
    NOME_PLANILHA,
    OUTPUT_DIR,
    SPREADSHEET_ID,
    PROCESSED_REGISTRY_FILE,
    SHEETS_SCOPES,
)
from data_source.google_utils import carregar_credenciais


logger = logging.getLogger(__name__)
COLUNAS_GASTOS = ["data", "descricao", "valor", "categoria"]
COLUNAS_CONTROLE = ["id_origem", "nome_arquivo", "origem", "processado_em"]
COLUNAS_TRANSACOES = [
    "id_transacao",
    "data",
    "descricao",
    "valor",
    "categoria",
    "banco",
    "arquivo_fatura",
    "origem",
    "tipo_lancamento",
]
NOME_ABA_CONSOLIDADAS = "TRANSACOES_CONSOLIDADAS"
NOME_ABA_2026 = "2026"
MESES_PT = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}


def _parse_valor_brl(valor: str) -> float | None:
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("\xa0", " ")
    texto = texto.replace("R$", "").replace("$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    texto = texto.replace(" ", "")
    if not texto:
        return None
    try:
        return float(texto)
    except Exception:
        return None


def _parse_header_mes(cabecalho: str) -> pd.Timestamp | None:
    texto = str(cabecalho).strip().lower()
    if not texto:
        return None

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))

    # suporta formatos como "abr.-26", "abril", "abril/2026", etc.
    if "janeiro" in texto or re.search(r"\bjan\b", texto):
        mes = 1
    elif "fevereiro" in texto or re.search(r"\bfev\b", texto):
        mes = 2
    elif "marco" in texto or re.search(r"\bmar\b", texto):
        mes = 3
    elif "abril" in texto or re.search(r"\babr\b", texto):
        mes = 4
    elif "maio" in texto or re.search(r"\bmai\b", texto):
        mes = 5
    elif "junho" in texto or re.search(r"\bjun\b", texto):
        mes = 6
    elif "julho" in texto or re.search(r"\bjul\b", texto):
        mes = 7
    elif "agosto" in texto or re.search(r"\bago\b", texto):
        mes = 8
    elif "setembro" in texto or re.search(r"\bset\b", texto):
        mes = 9
    elif "outubro" in texto or re.search(r"\bout\b", texto):
        mes = 10
    elif "novembro" in texto or re.search(r"\bnov\b", texto):
        mes = 11
    elif "dezembro" in texto or re.search(r"\bdez\b", texto):
        mes = 12
    else:
        return None

    match_ano = re.search(r"\b(20\d{2}|\d{2})\b", texto)
    if match_ano:
        ano = int(match_ano.group(1))
        if ano < 100:
            ano += 2000
    else:
        # aba 2026 sem ano explícito no cabeçalho das colunas
        ano = 2026

    return pd.Timestamp(year=ano, month=mes, day=1)


def _normalizar_dataframe_gastos_largo(registros: list[list[str]]) -> pd.DataFrame:
    if not registros or len(registros) < 2:
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    cabecalho = registros[0]
    meses: list[tuple[int, pd.Timestamp]] = []
    for idx, nome_coluna in enumerate(cabecalho):
        data_mes = _parse_header_mes(nome_coluna)
        if data_mes is not None:
            meses.append((idx, data_mes))

    if not meses:
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    # Prefer explicit April 2026 column (abr.-26) if present
    coluna_abril_idx = None
    coluna_abril_data: pd.Timestamp | None = None
    for idx, data_mes in meses:
        if data_mes.year == 2026 and data_mes.month == 4:
            coluna_abril_idx = idx
            coluna_abril_data = data_mes
            break

    if coluna_abril_idx is None:
        # Nenhuma coluna de abril encontrada — não extrairemos dados neste momento
        logger.info("Nenhuma coluna de abril encontrada na aba; retornando vazio.")
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    linhas: list[dict[str, object]] = []

    for linha in registros[1:]:
        descricao = str(linha[0]).strip() if len(linha) > 0 else ""
        if not descricao:
            continue
        if descricao.lower().startswith("total"):
            continue
        descricao_normalizada = descricao.lower()
        if "fatura mercado pago" in descricao_normalizada or "fatura santander" in descricao_normalizada:
            continue

        if coluna_abril_idx >= len(linha):
            continue

        valor = _parse_valor_brl(linha[coluna_abril_idx])
        if valor is None or valor == 0:
            continue

        categoria_base = descricao
        linhas.append(
            {
                "data": coluna_abril_data,
                "descricao": descricao,
                "valor": valor,
                "categoria": normalizar_categoria(categoria_base, descricao=descricao),
            }
        )

    if not linhas:
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    df = pd.DataFrame(linhas)
    return _normalizar_dataframe_gastos(df)


def _abrir_cliente():
    credenciais = carregar_credenciais(SHEETS_SCOPES)
    if credenciais is None:
        return None
    try:
        import gspread

        return gspread.authorize(credenciais)
    except Exception as exc:
        logger.warning("Falha ao inicializar cliente Google Sheets: %s", exc)
        return None


def _abrir_planilha(cliente, nome_planilha: str):
    try:
        if SPREADSHEET_ID:
            return cliente.open_by_key(SPREADSHEET_ID)
        return cliente.open(nome_planilha)
    except Exception as exc:
        logger.warning("Falha ao abrir planilha %s: %s", nome_planilha, exc)
        return None


def _obter_worksheet(planilha, nome_aba: str, criar: bool = False):
    try:
        return planilha.worksheet(nome_aba)
    except Exception:
        if not criar:
            return None
        try:
            return planilha.add_worksheet(title=nome_aba, rows=1000, cols=20)
        except Exception as exc:
            logger.warning("Falha ao criar aba %s: %s", nome_aba, exc)
            return None


def _normalizar_dataframe_gastos(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]

    faltantes = [col for col in COLUNAS_GASTOS if col not in df.columns]
    if faltantes:
        raise ValueError(f"A planilha não possui todas as colunas esperadas. Faltando: {', '.join(faltantes)}")

    df = df[COLUNAS_GASTOS].copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["descricao"] = df["descricao"].astype(str).str.strip()
    df["categoria"] = df["categoria"].astype(str).str.strip().replace("", "Outros")
    df = df.dropna(subset=["data", "descricao", "valor"])
    return df


def ler_gastos(nome_aba: str | None = None) -> pd.DataFrame:
    """Lê gastos da planilha Google (default: aba "2026") ou retorna DataFrame vazio como fallback."""
    aba_leitura = nome_aba or NOME_ABA_2026
    cliente = _abrir_cliente()
    if cliente is None:
        logger.warning("Cliente Google Sheets não disponível; retornando DataFrame vazio.")
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    planilha = _abrir_planilha(cliente, NOME_PLANILHA)
    if planilha is None:
        logger.warning("Planilha não encontrada; retornando DataFrame vazio.")
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    aba = _obter_worksheet(planilha, aba_leitura, criar=False)
    if aba is None:
        logger.warning("Aba '%s' não encontrada; retornando DataFrame vazio.", aba_leitura)
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    try:
        registros = aba.get_all_values()
    except Exception as exc:
        logger.warning("Falha ao ler valores da aba '%s': %s", aba_leitura, exc)
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    if not registros:
        logger.info("Aba '%s' vazia; retornando DataFrame vazio.", aba_leitura)
        return pd.DataFrame(columns=COLUNAS_GASTOS)

    try:
        cabecalho = [str(col).strip().lower() for col in registros[0]]
        colunas_esperadas = set(COLUNAS_GASTOS)

        if colunas_esperadas.issubset(set(cabecalho)):
            df = pd.DataFrame(registros[1:], columns=registros[0])
            df = _normalizar_dataframe_gastos(df)
            logger.info("Lidos %d registros da aba '%s' (formato tabular).", len(df), aba_leitura)
            return df

        df = _normalizar_dataframe_gastos_largo(registros)
        logger.info("Lidos %d registros da aba '%s' (formato mensal).", len(df), aba_leitura)
        return df
    except ValueError as exc:
        logger.warning("Erro ao normalizar dados da aba '%s': %s", aba_leitura, exc)
        return pd.DataFrame(columns=COLUNAS_GASTOS)


def _arquivo_registro_local() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return PROCESSED_REGISTRY_FILE


def _carregar_ids_transacoes_sheets() -> set[str]:
    """Carrega IDs de transações já existentes em TRANSACOES_CONSOLIDADAS."""
    cliente = _abrir_cliente()
    if cliente is None:
        return set()

    planilha = _abrir_planilha(cliente, NOME_PLANILHA)
    if planilha is None:
        return set()

    aba = _obter_worksheet(planilha, NOME_ABA_CONSOLIDADAS, criar=False)
    if aba is None:
        return set()

    try:
        registros = aba.get_all_records()
        ids_existentes: set[str] = set()
        for row in registros:
            id_transacao = str(row.get("id_transacao", "")).strip()
            if id_transacao:
                ids_existentes.add(id_transacao)
        logger.info("Carregados %d IDs de transações já existentes.", len(ids_existentes))
        return ids_existentes
    except Exception as exc:
        logger.warning("Falha ao carregar IDs de transações: %s", exc)
        return set()


def carregar_processados() -> set[str]:
    """Carrega IDs de processamento já registrados, priorizando Google Sheets."""
    cliente = _abrir_cliente()
    if cliente is None:
        return _carregar_processados_local()

    planilha = _abrir_planilha(cliente, NOME_PLANILHA)
    if planilha is None:
        return _carregar_processados_local()

    aba = _obter_worksheet(planilha, NOME_ABA_CONTROLE, criar=False)
    if aba is None:
        return _carregar_processados_local()

    try:
        registros = aba.get_all_records()
    except Exception:
        return _carregar_processados_local()

    processados: set[str] = set()
    for row in registros:
        valor = str(row.get("id_origem", "")).strip()
        if valor:
            processados.add(valor)
    return processados


def _carregar_processados_local() -> set[str]:
    caminho = _arquivo_registro_local()
    if not caminho.exists():
        return set()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return set(dados.get("ids", []))
    except Exception:
        return set()


def _salvar_processados_local(ids: Iterable[str]) -> None:
    caminho = _arquivo_registro_local()
    caminho.write_text(json.dumps({"ids": sorted(set(ids))}, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_processado(id_origem: str, nome_arquivo: str, origem: str) -> None:
    """Registra um arquivo processado no Google Sheets ou localmente."""
    cliente = _abrir_cliente()
    if cliente is None:
        ids = _carregar_processados_local()
        ids.add(id_origem)
        _salvar_processados_local(ids)
        return

    planilha = _abrir_planilha(cliente, NOME_PLANILHA)
    if planilha is None:
        ids = _carregar_processados_local()
        ids.add(id_origem)
        _salvar_processados_local(ids)
        return

    aba = _obter_worksheet(planilha, NOME_ABA_CONTROLE, criar=True)
    if aba is None:
        ids = _carregar_processados_local()
        ids.add(id_origem)
        _salvar_processados_local(ids)
        return

    try:
        linhas = aba.get_all_records()
        if not linhas:
            aba.append_row(COLUNAS_CONTROLE)
        else:
            colunas_atuais = [str(col).strip().lower() for col in aba.row_values(1)]
            if not colunas_atuais or "id_origem" not in colunas_atuais:
                aba.update("A1:D1", [COLUNAS_CONTROLE])
    except Exception:
        pass

    try:
        # evita duplicar linhas no controle
        existentes = carregar_processados()
        if id_origem in existentes:
            return
        aba.append_row([id_origem, nome_arquivo, origem, pd.Timestamp.utcnow().isoformat()])
    except Exception as exc:
        logger.warning("Falha ao registrar processamento no Google Sheets: %s", exc)
        ids = _carregar_processados_local()
        ids.add(id_origem)
        _salvar_processados_local(ids)


def inserir_transacoes_sheets(df: pd.DataFrame) -> tuple[int, int]:
    """
    Sincroniza TRANSACOES_CONSOLIDADAS com o consolidado local, evitando duplicatas.

    Retorna tupla (inseridas, puladas).
    """
    if df.empty:
        logger.info("DataFrame vazio; nenhuma transação para inserir.")
        return 0, 0

    cliente = _abrir_cliente()
    if cliente is None:
        logger.warning("Cliente Google Sheets não disponível; não inserindo.")
        return 0, len(df)

    planilha = _abrir_planilha(cliente, NOME_PLANILHA)
    if planilha is None:
        logger.warning("Planilha não encontrada; não inserindo.")
        return 0, len(df)

    aba = _obter_worksheet(planilha, NOME_ABA_CONSOLIDADAS, criar=True)
    if aba is None:
        logger.warning("Não foi possível abrir/criar aba '%s'.", NOME_ABA_CONSOLIDADAS)
        return 0, len(df)

    ids_existentes = _carregar_ids_transacoes_sheets()

    df_export = df.copy()
    for col in COLUNAS_TRANSACOES:
        if col not in df_export.columns:
            if col == "categoria":
                df_export[col] = "Outros"
            elif col == "banco":
                df_export[col] = "generico"
            elif col == "arquivo_fatura":
                df_export[col] = ""
            elif col == "origem":
                df_export[col] = "fatura_pdf"
            elif col == "tipo_lancamento":
                df_export[col] = "compra"
            else:
                df_export[col] = ""

    df_export = df_export[COLUNAS_TRANSACOES].copy()

    try:
        df_export["data"] = pd.to_datetime(df_export["data"], errors="coerce").dt.strftime("%Y-%m-%d")
        df_export["valor"] = pd.to_numeric(df_export["valor"], errors="coerce")
        df_export = df_export.dropna(subset=["id_transacao", "data", "descricao", "valor"]).copy()

        ids_export = df_export["id_transacao"].astype(str)
        novos = df_export.loc[~ids_export.isin(ids_existentes)].copy()
        puladas = int(len(df_export) - len(novos))

        if novos.empty:
            logger.info("Planilha '%s' já está atualizada; nenhuma transação nova para inserir.", NOME_ABA_CONSOLIDADAS)
            return 0, puladas

        if not aba.get_all_values():
            aba.append_row(COLUNAS_TRANSACOES)

        linhas = []
        for _, row in novos.iterrows():
            linhas.append(
                [
                    str(row["id_transacao"]),
                    str(row["data"]),
                    str(row["descricao"]),
                    float(row["valor"]),
                    str(row["categoria"]),
                    str(row["banco"]),
                    str(row["arquivo_fatura"]),
                    str(row["origem"]),
                    str(row["tipo_lancamento"]),
                ]
            )

        aba.append_rows(linhas, value_input_option="USER_ENTERED")

        inseridas = len(linhas)
        logger.info("Planilha '%s' recebeu %d novas transações.", NOME_ABA_CONSOLIDADAS, inseridas)
        return inseridas, puladas

    except Exception as exc:
        logger.warning("Falha ao sincronizar transações em Google Sheets: %s", exc)
        return 0, len(df)
