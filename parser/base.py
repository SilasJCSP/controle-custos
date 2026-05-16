from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import re
from typing import Iterable

import pandas as pd
import pdfplumber

from utils.text import normalizar_descricao


logger = logging.getLogger(__name__)
LINHA_DATA_RE = re.compile(r"^(?P<data>\d{2}/\d{2}(?:/\d{4})?|\d{4}-\d{2}-\d{2})\s+")
VALOR_RE = re.compile(r"(?P<valor>-?\(?R?\$?\s?\d[\d\.\s]*[\.,]\d{2}\)?)$")


@dataclass(frozen=True)
class ParseContext:
    arquivo_fatura: str
    banco: str
    ano_referencia: int | None = None


class BaseParser:
    banco: str = "generico"

    def parse_text(self, texto: str, arquivo: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        raise NotImplementedError()


def detectar_banco_por_texto(texto: str, caminho_pdf: Path) -> str:
    base = f"{caminho_pdf.stem} {texto}".lower()
    if "mercado pago" in base or "mercado" in base:
        return "mercado_pago"
    if "santander" in base:
        return "santander"
    if "nubank" in base:
        return "nubank"
    if "itau" in base or "itaú" in base:
        return "itau"
    return "generico"


def extrair_texto_pdf(caminho_pdf: Path) -> str:
    partes: list[str] = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes)


def tentar_ocr_mock(caminho_pdf: Path) -> str:
    """Interface preparada para OCR. Por enquanto apenas registra e retorna vazio."""
    logger.info("OCR ainda não habilitado para %s; retornando texto vazio.", caminho_pdf.name)
    return ""


def _limpar_linha(linha: str) -> str:
    return re.sub(r"\s+", " ", (linha or "").strip())


def _linha_inicio_transacao(linha: str) -> bool:
    return bool(LINHA_DATA_RE.match(linha))


def _parse_valor(valor_texto: str) -> float:
    negativo = "(" in valor_texto and ")" in valor_texto
    limpo = re.sub(r"[^\d,\.\-]", "", valor_texto)
    if "," in limpo and "." in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")
    valor = float(limpo)
    return -abs(valor) if negativo else valor


def _extrair_transacao_linha(linha: str, contexto: ParseContext) -> dict[str, object] | None:
    match_data = LINHA_DATA_RE.match(linha)
    match_valor = VALOR_RE.search(linha)
    if not match_data or not match_valor:
        return None

    data_str = match_data.group("data")
    valor_str = match_valor.group("valor")
    descricao = linha[len(data_str):].strip()
    descricao = descricao[: -len(valor_str)].strip() if valor_str else descricao
    descricao = " ".join(descricao.split())

    if not descricao:
        return None

    data = _parse_data(data_str, contexto.ano_referencia)
    if pd.isna(data):
        logger.debug("Data inválida descartada no parser %s: %s", contexto.banco, linha)
        return None

    try:
        valor = _parse_valor(valor_str)
    except Exception:
        logger.debug("Valor inválido descartado no parser %s: %s", contexto.banco, linha)
        return None

    return {
        "data": data.date(),
        "descricao": descricao,
        "valor": valor,
        "banco": contexto.banco,
        "arquivo_fatura": contexto.arquivo_fatura,
    }


def _parse_data(data_texto: str, ano_referencia: int | None = None) -> pd.Timestamp:
    if re.fullmatch(r"\d{2}/\d{2}", data_texto):
        ano = ano_referencia or pd.Timestamp.today().year
        return pd.to_datetime(f"{data_texto}/{ano}", format="%d/%m/%Y", errors="coerce")
    return pd.to_datetime(data_texto, dayfirst=True, errors="coerce")


def extrair_transacoes_basicas(
    linhas: Iterable[str],
    contexto: ParseContext,
) -> pd.DataFrame:
    """Extrai transações de linhas com padrão data + descrição + valor."""
    transacoes: list[dict[str, object]] = []
    linhas_convertidas = 0
    linhas_descartadas = 0
    buffer_linha = ""

    for linha in linhas:
        linha = _limpar_linha(linha)
        if not linha:
            continue

        candidatos = [linha]
        if buffer_linha:
            candidatos.insert(0, f"{buffer_linha} {linha}")

        transacao = None
        for candidato in candidatos:
            transacao = _extrair_transacao_linha(candidato, contexto)
            if transacao:
                break

        if transacao:
            transacoes.append(transacao)
            linhas_convertidas += 1
            buffer_linha = ""
            continue

        if _linha_inicio_transacao(linha):
            buffer_linha = linha
            continue

        linhas_descartadas += 1
        logger.debug("Linha descartada no parser %s: %s", contexto.banco, linha)

    if buffer_linha:
        transacao = _extrair_transacao_linha(buffer_linha, contexto)
        if transacao:
            transacoes.append(transacao)
            linhas_convertidas += 1
        else:
            linhas_descartadas += 1
            logger.debug("Buffer descartado no parser %s: %s", contexto.banco, buffer_linha)

    logger.info(
        "%s [%s]: %d linhas convertidas, %d descartadas",
        contexto.arquivo_fatura,
        contexto.banco,
        linhas_convertidas,
        linhas_descartadas,
    )

    if not transacoes:
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    df = pd.DataFrame(transacoes)
    df = df.drop_duplicates(subset=["data", "descricao", "valor", "banco", "arquivo_fatura"]).reset_index(drop=True)
    return df


def normalizar_dataframe_parsado(df: pd.DataFrame, banco: str, arquivo_fatura: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    df = df.copy()
    if "banco" not in df.columns:
        df["banco"] = banco
    if "arquivo_fatura" not in df.columns:
        df["arquivo_fatura"] = arquivo_fatura

    df["descricao"] = df["descricao"].astype(str).str.strip()
    df["descricao_norm"] = df["descricao"].apply(normalizar_descricao)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["data", "descricao", "valor"]).copy()
    return df[["data", "descricao", "valor", "banco", "arquivo_fatura"]]
