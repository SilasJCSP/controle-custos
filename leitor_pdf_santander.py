"""Parser específico para faturas Santander."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import pdfplumber

REGEX_SANTANDER = re.compile(
    r"^(?P<data>\d{2}/\d{2})\s+(?P<descricao>.+?)\s+"
    r"(?P<valor>-?\(?R?\$?\s?\d{1,3}(?:[\.]\d{3})*(?:[\.,]\d{2})\)?)$"
)
REGEX_MULTI_TRANSACAO = re.compile(
    r"(?P<data>\d{2}/\d{2})\s+"
    r"(?P<descricao>.+?)\s+"
    r"(?P<valor>-?\(?R?\$?\s?\d{1,3}(?:[\.]\d{3})*(?:[\.,]\d{2})\)?)"
    r"(?=\s+\d{2}/\d{2}\s+|$)"
)

INICIO_DATA_RE = re.compile(r"^\d{2}/\d{2}\b")
INICIO_SECAO_TABELA_RE = re.compile(r"^data\s+movimenta(?:ç|c)[õo]es\s+valor\s+em\s+r\$", re.IGNORECASE)
FIM_SECAO_TABELA_RE = re.compile(
    r"^total\s+r\$|^silas\s+lopes$|^vencimento:|^seu cart[aã]o de cr[eé]dito|^op[cç][õo]es de pagamento|^datas importantes",
    re.IGNORECASE,
)
RUIDO_DESCRICAO_RE = re.compile(
    r"parcelamento|pagamento m[ií]nimo|pagamento total|total da fatura|fatura aberta|central cob|ft-ci|valor total|anuidade diferenciada",
    flags=re.IGNORECASE,
)
DATA_EMBUTIDA_RE = re.compile(r"\s\d{2}/\d{2}(?:/\d{2,4})?\b")
RUIDO_LINHA_RE = re.compile(r"pagamento e demais cr[eé]ditos", re.IGNORECASE)
DESCRICAO_NUM_FINAL_RE = re.compile(r"^(?P<texto>.+?)\s+(?P<numero>\d{1,3})$")


def _limpar_linha(linha: str) -> str:
    linha = linha.strip()
    return re.sub(r"\s+", " ", linha)


def _parse_valor(valor_str: str) -> float:
    negativo_parenteses = "(" in valor_str and ")" in valor_str

    limpo = re.sub(r"[^\d,.-]", "", valor_str)

    if "," in limpo and "." in limpo:
        # Formato brasileiro com milhar em ponto e decimal em vírgula
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")
    elif limpo.count(".") > 1:
        # Ex.: 1.234.56 (ruído): remove separadores extras
        partes = limpo.split(".")
        limpo = "".join(partes[:-1]) + "." + partes[-1]

    valor = float(limpo)
    if negativo_parenteses or valor < 0:
        return -abs(valor)
    return valor


def _parse_data(data_str: str, ano: int) -> pd.Timestamp:
    return pd.to_datetime(f"{data_str}/{ano}", format="%d/%m/%Y", errors="coerce")


def _linha_valida_descricao(descricao: str) -> bool:
    if RUIDO_DESCRICAO_RE.search(descricao):
        return False
    if DATA_EMBUTIDA_RE.search(descricao):
        return False
    return True


def _valor_util(valor: float) -> bool:
    """Descarta lançamentos sem impacto financeiro (ex.: valor zero)."""
    return abs(valor) > 0.000001


def _reconciliar_descricao_valor(descricao: str, valor: float) -> tuple[str, float]:
    """Mantém descrição e valor originais.

    Observação: números ao final da descrição podem fazer parte do nome da compra
    (ex.: estabelecimento/identificador), então não devem ser movidos para valor.
    """
    texto = " ".join((descricao or "").strip().split())
    return texto, valor


def _extrair_da_linha(linha: str, ano_referencia: int) -> dict[str, object] | None:
    match = REGEX_SANTANDER.match(linha)
    if not match:
        return None

    data_str = match.group("data")
    descricao = " ".join(match.group("descricao").strip().split())
    valor_str = match.group("valor")

    if not _linha_valida_descricao(descricao):
        return None

    data = _parse_data(data_str, ano_referencia)
    if pd.isna(data):
        return None

    try:
        valor = _parse_valor(valor_str)
    except ValueError:
        return None

    descricao, valor = _reconciliar_descricao_valor(descricao, valor)

    if not _valor_util(valor):
        return None

    return {"data": data.date(), "descricao": descricao, "valor": valor}


def _extrair_multiplas_da_linha(linha: str, ano_referencia: int) -> list[dict[str, object]]:
    """Extrai múltiplas transações quando o PDF cola vários lançamentos em uma linha."""
    achados: list[dict[str, object]] = []

    for match in REGEX_MULTI_TRANSACAO.finditer(linha):
        data_str = match.group("data")
        descricao = " ".join(match.group("descricao").strip().split())
        valor_str = match.group("valor")

        if not _linha_valida_descricao(descricao):
            continue

        data = _parse_data(data_str, ano_referencia)
        if pd.isna(data):
            continue

        try:
            valor = _parse_valor(valor_str)
        except ValueError:
            continue

        descricao, valor = _reconciliar_descricao_valor(descricao, valor)

        if not _valor_util(valor):
            continue

        achados.append({"data": data.date(), "descricao": descricao, "valor": valor})

    return achados


def _extrair_linhas_secao_tabela(linhas: list[str]) -> list[str]:
    """Recorta apenas linhas dentro da seção de transações da tabela Santander."""
    secao_linhas: list[str] = []
    em_secao = False

    for linha in linhas:
        linha = _limpar_linha(linha)
        if not linha:
            continue

        if INICIO_SECAO_TABELA_RE.search(linha):
            em_secao = True
            continue

        if not em_secao:
            continue

        if FIM_SECAO_TABELA_RE.search(linha) and not INICIO_DATA_RE.match(linha):
            em_secao = False
            continue

        secao_linhas.append(linha)

    return secao_linhas


def _extrair_transacoes_de_linhas(linhas: list[str], ano_referencia: int) -> tuple[list[dict[str, object]], int]:
    """Extrai transações de uma lista de linhas com suporte a quebra de linha."""
    transacoes: list[dict[str, object]] = []
    linhas_convertidas = 0
    buffer = ""

    for linha in linhas:
        linha = _limpar_linha(linha)
        if not linha:
            continue

        if RUIDO_LINHA_RE.search(linha):
            continue

        transacao = _extrair_da_linha(linha, ano_referencia)
        if transacao:
            linhas_convertidas += 1
            transacoes.append(transacao)
            buffer = ""
            continue

        multiplas = _extrair_multiplas_da_linha(linha, ano_referencia)
        if multiplas:
            linhas_convertidas += len(multiplas)
            transacoes.extend(multiplas)
            buffer = ""
            continue

        if buffer and INICIO_DATA_RE.match(linha):
            buffer = linha
            continue

        if buffer:
            linha_combinada = f"{buffer} {linha}"
            transacao = _extrair_da_linha(linha_combinada, ano_referencia)
            if transacao:
                linhas_convertidas += 1
                transacoes.append(transacao)
                buffer = ""
                continue

            multiplas = _extrair_multiplas_da_linha(linha_combinada, ano_referencia)
            if multiplas:
                linhas_convertidas += len(multiplas)
                transacoes.extend(multiplas)
                buffer = ""
                continue

        if INICIO_DATA_RE.match(linha):
            buffer = linha

    return transacoes, linhas_convertidas


def extrair_transacoes_santander(caminho_pdf: Path, ano_referencia: int) -> pd.DataFrame:
    """Extrai transações de fatura Santander com heurística de linha quebrada."""
    if not caminho_pdf.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

    transacoes: list[dict[str, object]] = []
    total_linhas = 0
    linhas_convertidas = 0
    linhas_todas_paginas: list[str] = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            linhas_pagina = texto.splitlines()
            linhas_todas_paginas.extend(linhas_pagina)
            total_linhas += len(linhas_pagina)

    # 1) Prioriza seção de tabela de movimentações.
    linhas_secao_tabela = _extrair_linhas_secao_tabela(linhas_todas_paginas)
    transacoes_tabela, convertidas_tabela = _extrair_transacoes_de_linhas(
        linhas_secao_tabela,
        ano_referencia,
    )

    # 2) Fallback global para capturar casos fora da seção esperada.
    transacoes_fallback, convertidas_fallback = _extrair_transacoes_de_linhas(
        linhas_todas_paginas,
        ano_referencia,
    )

    transacoes = transacoes_tabela + transacoes_fallback
    linhas_convertidas = convertidas_tabela + convertidas_fallback

    if transacoes:
        df_transacoes = pd.DataFrame(transacoes)
        df_transacoes = df_transacoes.drop_duplicates(subset=["data", "descricao", "valor"]).reset_index(drop=True)
    else:
        df_transacoes = pd.DataFrame(columns=["data", "descricao", "valor"])

    logging.info(
        "%s [santander]: %d/%d linhas convertidas (tabela=%d, fallback=%d)",
        caminho_pdf.name,
        linhas_convertidas,
        total_linhas,
        convertidas_tabela,
        convertidas_fallback,
    )

    if df_transacoes.empty:
        logging.warning("Nenhuma transação Santander encontrada em %s", caminho_pdf.name)
        return pd.DataFrame(columns=["data", "descricao", "valor"])

    return df_transacoes
