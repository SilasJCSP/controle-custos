"""Leitura de faturas PDF e extração simples de transações."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import pdfplumber
from leitor_pdf_santander import extrair_transacoes_santander


# Padrão tolerante para:
# 12/03 MERCADO XPTO 120,50
# 12/03/2026 UBER TRIP 45,90
# 2026-03-12 IFOOD 89.90
LINHA_TRANSACAO_RE = re.compile(
    r"^(?P<data>\d{2}/\d{2}(?:/\d{4})?|\d{4}-\d{2}-\d{2})\s+"
    r"(?P<descricao>.+?)\s+"
    r"(?P<valor>-?\(?R?\$?\s?\d[\d\.\s]*[\.,]\d{2}\)?)$"
)

LINHA_INICIO_DATA_RE = re.compile(r"^(\d{2}/\d{2}(?:/\d{4})?|\d{4}-\d{2}-\d{2})")


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _limpar_linha(linha: str) -> str:
    """Remove espaços extras para melhorar o matching das regex."""
    linha = linha.strip()
    linha = re.sub(r"\s+", " ", linha)
    return linha


def _inferir_ano_por_arquivo(caminho_pdf: Path) -> int | None:
    """Tenta inferir ano pelo nome do arquivo (ex.: fatura_2025_12.pdf)."""
    match = re.search(r"(19\d{2}|20\d{2})", caminho_pdf.stem)
    if not match:
        return None
    return int(match.group(1))


def _detectar_banco(texto_total: str, caminho_pdf: Path) -> str:
    """Detecta banco/provedor de forma heurística para aplicar parser adequado."""
    base = f"{caminho_pdf.stem} {texto_total}".lower()
    if "mercado pago" in base:
        return "mercado_pago"
    if "santander" in base:
        return "santander"
    if "nubank" in base:
        return "nubank"
    if "itau" in base or "itaú" in base:
        return "itau"
    return "generico"


def _anexar_origem_fatura(df: pd.DataFrame, banco: str, caminho_pdf: Path) -> pd.DataFrame:
    """Anexa metadados de origem (banco e arquivo) às transações extraídas."""
    if df.empty:
        return df

    df_saida = df.copy()
    df_saida["banco"] = banco
    df_saida["arquivo_fatura"] = caminho_pdf.name
    return df_saida


def _linha_candidata_transacao(linha: str) -> bool:
    """Identifica se a linha tem formato mínimo para tentar parse de transação."""
    return bool(LINHA_INICIO_DATA_RE.match(linha))


def _normalizar_valor(valor_texto: str) -> float:
    """Converte string de valor para float, aceitando vírgula ou ponto."""
    negativo = "(" in valor_texto and ")" in valor_texto

    limpo = re.sub(r"[^\d,\.\-]", "", valor_texto)

    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")

    valor = float(limpo)
    return -abs(valor) if negativo else valor


def _normalizar_data(data_texto: str, ano_referencia: int | None = None) -> pd.Timestamp:
    """Normaliza datas aceitando dd/mm, dd/mm/yyyy e yyyy-mm-dd."""
    data_texto = str(data_texto).strip()
    ano = ano_referencia or pd.Timestamp.today().year

    if re.fullmatch(r"\d{2}/\d{2}", data_texto):
        return pd.to_datetime(f"{data_texto}/{ano}", format="%d/%m/%Y", errors="coerce")

    return pd.to_datetime(data_texto, dayfirst=True, errors="coerce")


def _ajustar_sinal_valor(descricao: str, valor_texto: str, valor: float) -> float:
    """Aplica heurística de sinal para créditos/estornos e valores parentetizados."""
    texto_desc = (descricao or "").lower()
    texto_valor = (valor_texto or "").strip().lower()

    if texto_valor.startswith("-") or ("(" in texto_valor and ")" in texto_valor):
        return -abs(valor)

    marcadores_credito = ["estorno", "crédito", "credito", "pagamento recebido", "ajuste a credito"]
    if any(marcador in texto_desc for marcador in marcadores_credito):
        return -abs(valor)

    return valor


def _extrair_transacao_linha(linha: str, ano_referencia: int | None = None) -> dict[str, object] | None:
    """Tenta extrair uma transação a partir de uma linha textual da fatura."""
    match = LINHA_TRANSACAO_RE.match(linha)
    if not match:
        return None

    data_str = match.group("data")
    descricao = " ".join(match.group("descricao").strip().split())
    valor_str = match.group("valor")

    data = _normalizar_data(data_str, ano_referencia=ano_referencia)
    if pd.isna(data):
        return None

    try:
        valor = _normalizar_valor(valor_str)
    except ValueError:
        return None

    valor = _ajustar_sinal_valor(descricao, valor_str, valor)
    return {"data": data.date(), "descricao": descricao, "valor": valor}


def _extrair_transacoes_linhas(
    linhas: list[str],
    ano_referencia: int | None = None,
) -> tuple[list[dict[str, object]], int, int]:
    """Extrai transações a partir de uma lista de linhas, com suporte a linha quebrada."""
    linhas_extraidas: list[dict[str, object]] = []
    total_linhas = 0
    linhas_convertidas = 0
    buffer = ""

    for linha in linhas:
        total_linhas += 1
        linha = _limpar_linha(linha)
        if not linha:
            continue

        if not buffer and not _linha_candidata_transacao(linha):
            continue

        transacao = None

        if _linha_candidata_transacao(linha):
            transacao = _extrair_transacao_linha(linha, ano_referencia=ano_referencia)
            if transacao:
                linhas_convertidas += 1
                linhas_extraidas.append(transacao)
                buffer = ""
                continue

            if buffer:
                # Evita combinar duas linhas candidatas (gera contaminação de descrição).
                transacao_buffer = _extrair_transacao_linha(
                    buffer,
                    ano_referencia=ano_referencia,
                )
                if transacao_buffer:
                    linhas_convertidas += 1
                    linhas_extraidas.append(transacao_buffer)
                buffer = linha
                continue

        if buffer:
            linha_combinada = f"{buffer} {linha}"
            transacao = _extrair_transacao_linha(
                linha_combinada,
                ano_referencia=ano_referencia,
            )
            if transacao:
                linhas_convertidas += 1
                linhas_extraidas.append(transacao)
                buffer = ""
                continue

        if _linha_candidata_transacao(linha):
            buffer = linha

    if buffer:
        transacao = _extrair_transacao_linha(buffer, ano_referencia=ano_referencia)
        if transacao:
            linhas_convertidas += 1
            linhas_extraidas.append(transacao)

    return linhas_extraidas, linhas_convertidas, total_linhas


def _filtrar_transacoes_por_banco(df: pd.DataFrame, banco: str) -> pd.DataFrame:
    """Remove falsos positivos de acordo com o tipo de fatura identificado."""
    if df.empty:
        return df

    filtrado = df.copy()
    descricoes = filtrado["descricao"].astype(str)

    if banco == "santander":
        ruido = descricoes.str.contains(
            r"parcelamento de fatura|central cob|ft-ci|fatura aberta|pagamento minimo|pagamento total",
            case=False,
            regex=True,
        )
        data_embutida = descricoes.str.contains(
            r"\s\d{2}/\d{2}(?:/\d{2,4})?\b|\s\d{4}-\d{2}-\d{2}\b",
            case=False,
            regex=True,
        )
        filtrado = filtrado.loc[~(ruido | data_embutida)].copy()

    return filtrado.reset_index(drop=True)



def extrair_transacoes_pdf(caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
    """Extrai transações de um único PDF e retorna DataFrame com data, descricao, valor."""
    if not caminho_pdf.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho_pdf}")

    ano_efetivo = (
        ano_referencia if ano_referencia is not None else _inferir_ano_por_arquivo(caminho_pdf)
    )
    linhas_extraidas: list[dict[str, object]] = []
    total_linhas = 0
    linhas_convertidas = 0
    textos_paginas: list[str] = []

    # Primeira leitura: identificar banco e decidir parser especializado.
    with pdfplumber.open(caminho_pdf) as pdf:
        if not pdf.pages:
            return pd.DataFrame(columns=["data", "descricao", "valor"])

        textos_paginas = [(pagina.extract_text() or "") for pagina in pdf.pages]

    banco = _detectar_banco("\n".join(textos_paginas), caminho_pdf)
    logging.info("%s: parser detectado = %s", caminho_pdf.name, banco)

    if banco == "santander":
        ano_parser = ano_efetivo or pd.Timestamp.today().year
        df_santander = extrair_transacoes_santander(caminho_pdf, ano_referencia=ano_parser)
        return _anexar_origem_fatura(df_santander, banco=banco, caminho_pdf=caminho_pdf)

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            linhas = texto.splitlines()
            extraidas_pagina, convertidas_pagina, total_pagina = _extrair_transacoes_linhas(
                linhas,
                ano_referencia=ano_efetivo,
            )
            linhas_extraidas.extend(extraidas_pagina)
            linhas_convertidas += convertidas_pagina
            total_linhas += total_pagina

    logging.info(
        "%s: %d/%d linhas convertidas",
        caminho_pdf.name,
        linhas_convertidas,
        total_linhas,
    )

    if not linhas_extraidas:
        logging.info("Nenhuma transação extraída de: %s", caminho_pdf.name)
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    df_transacoes = pd.DataFrame(linhas_extraidas)
    df_transacoes = _filtrar_transacoes_por_banco(df_transacoes, banco)
    df_transacoes = _anexar_origem_fatura(df_transacoes, banco=banco, caminho_pdf=caminho_pdf)
    return df_transacoes


def ler_pasta_faturas(pasta_faturas: Path, ano_referencia: int | None = None) -> pd.DataFrame:
    """Lê todos os PDFs da pasta informada e consolida transações em um DataFrame."""
    if not pasta_faturas.exists():
        raise FileNotFoundError(f"Pasta de faturas não encontrada: {pasta_faturas}")

    arquivos_pdf = sorted(pasta_faturas.glob("*.pdf"))
    if not arquivos_pdf:
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    frames = []
    for arquivo_pdf in arquivos_pdf:
        try:
            df_pdf = extrair_transacoes_pdf(arquivo_pdf, ano_referencia=ano_referencia)
            if not df_pdf.empty:
                frames.append(df_pdf)
        except Exception as erro:
            logging.warning("Falha ao processar %s: %s", arquivo_pdf.name, erro)

    if not frames:
        return pd.DataFrame(columns=["data", "descricao", "valor", "banco", "arquivo_fatura"])

    consolidado = pd.concat(frames, ignore_index=True)
    consolidado["data"] = pd.to_datetime(consolidado["data"], errors="coerce")
    consolidado = consolidado.sort_values(
        by=["banco", "arquivo_fatura", "data", "valor"],
        ascending=[True, True, False, False],
        na_position="last",
    ).reset_index(drop=True)
    return consolidado
