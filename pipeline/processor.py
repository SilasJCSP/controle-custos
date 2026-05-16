from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from categorias import categorizar
from categorias import normalizar_categoria
from config import OUTPUT_CSV, OUTPUT_DIR, OUTPUT_TRANSACOES_CSV
from data_source.drive import listar_faturas, ler_texto_fatura
from data_source.models import FaturaFonte
from data_source.sheets import carregar_processados, ler_gastos, registrar_processado, inserir_transacoes_sheets
from app.parsers import generico, mercado_pago, santander, nubank
from app.repositories.sqlite_repository import (
    buscar_transacoes,
    init_repository,
    registrar_banco,
    registrar_importacao,
    salvar_transacoes,
)
from utils.text import classificar_tipo_lancamento, gerar_id_transacao, normalizar_descricao
from validators.dataframe_validator import validar_schema_dataframe


logger = logging.getLogger(__name__)
COLUNAS_FINAIS = [
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


def _deve_ignorar_transacao(descricao: str) -> bool:
    texto = normalizar_descricao(descricao)
    if not texto:
        return False
    return any(
        trecho in texto
        for trecho in (
            "vr va",
            "vale refeicao",
            "vale alimentacao",
            "fatura mercado pago",
            "fatura santander",
        )
    )


def _garantir_colunas_finais(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_FINAIS)

    df = df.copy()
    for coluna in COLUNAS_FINAIS:
        if coluna not in df.columns:
            if coluna == "categoria":
                df[coluna] = "Outros"
            elif coluna == "banco":
                df[coluna] = "generico"
            elif coluna == "arquivo_fatura":
                df[coluna] = ""
            elif coluna == "origem":
                df[coluna] = "fatura_pdf"
            elif coluna == "tipo_lancamento":
                df[coluna] = "compra"
            else:
                df[coluna] = pd.NA

    df = df[COLUNAS_FINAIS].copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["descricao"] = df["descricao"].astype(str).str.strip()
    df["categoria"] = df["categoria"].astype(str).str.strip().replace("", "Outros")
    df["banco"] = df["banco"].astype(str).str.strip().replace("", "generico")
    df["arquivo_fatura"] = df["arquivo_fatura"].astype(str).str.strip()
    df["origem"] = df["origem"].astype(str).str.strip().replace("", "fatura_pdf")
    df["tipo_lancamento"] = df["tipo_lancamento"].astype(str).str.strip().replace("", "compra")
    df["categoria"] = df.apply(
        lambda row: normalizar_categoria(str(row["categoria"]), descricao=str(row["descricao"])),
        axis=1,
    )
    df = df.dropna(subset=["data", "descricao", "valor"]).copy()
    df = df[~df["descricao"].apply(_deve_ignorar_transacao)].copy()
    df = validar_schema_dataframe(df, COLUNAS_FINAIS)
    return df.reindex(columns=COLUNAS_FINAIS).reset_index(drop=True)


def _carregar_existentes() -> pd.DataFrame:
    df_sqlite = buscar_transacoes()
    if not df_sqlite.empty:
        return _garantir_colunas_finais(df_sqlite)

    if not OUTPUT_TRANSACOES_CSV.exists():
        return pd.DataFrame(columns=COLUNAS_FINAIS)

    try:
        df = pd.read_csv(OUTPUT_TRANSACOES_CSV)
    except Exception as exc:
        logger.warning("Falha ao ler CSV existente: %s", exc)
        return pd.DataFrame(columns=COLUNAS_FINAIS)

    return _garantir_colunas_finais(df)


def _gerar_ids_em_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    if "descricao" not in df.columns:
        df["descricao"] = ""
    df["data"] = pd.to_datetime(df.get("data"), errors="coerce")
    df["descricao_norm"] = df["descricao"].astype(str).apply(normalizar_descricao)
    df["id_transacao"] = df.apply(
        lambda row: gerar_id_transacao(row["data"], row.get("valor", 0), row["descricao_norm"]),
        axis=1,
    )
    return df


def _selecionar_parser(fonte: FaturaFonte, texto_bruto: str):
    banco = (fonte.banco or "").lower()
    if banco == "santander":
        return santander.parse
    if banco == "mercado_pago":
        return mercado_pago.parse
    if banco == "nubank":
        return nubank.parse

    texto = f"{fonte.nome_arquivo} {texto_bruto}".lower()
    if "santander" in texto:
        return santander.parse
    if "mercado" in texto:
        return mercado_pago.parse
    if "nubank" in texto:
        return nubank.parse
    return generico.parse


def _normalizar_transacoes(df: pd.DataFrame, origem: str, nome_arquivo: str, banco: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_FINAIS)

    df = df.copy()
    df["descricao"] = df["descricao"].astype(str).str.strip()
    df["descricao_norm"] = df["descricao"].apply(normalizar_descricao)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["categoria"] = df.get("categoria", pd.Series([None] * len(df)))
    if "categoria" not in df.columns:
        df["categoria"] = None

    df["categoria"] = df["categoria"].astype(str).replace({"nan": "", "None": ""}).str.strip()
    mascara_categoria_vazia = df["categoria"].isin(["", "nan", "None"])
    if mascara_categoria_vazia.any():
        df.loc[mascara_categoria_vazia, "categoria"] = df.loc[mascara_categoria_vazia, "descricao"].apply(categorizar)

    df["id_transacao"] = df.apply(
        lambda row: gerar_id_transacao(row["data"], row["valor"], row["descricao_norm"]),
        axis=1,
    )
    df["banco"] = df.get("banco", banco)
    df["banco"] = df["banco"].astype(str).replace({"nan": banco, "None": banco, "": banco})
    df["arquivo_fatura"] = df.get("arquivo_fatura", nome_arquivo)
    df["arquivo_fatura"] = df["arquivo_fatura"].astype(str).replace({"nan": nome_arquivo, "None": nome_arquivo, "": nome_arquivo})
    df["origem"] = origem
    df["tipo_lancamento"] = df.apply(
        lambda row: classificar_tipo_lancamento(str(row["descricao"]), float(row["valor"])),
        axis=1,
    )

    df = df[~df["descricao"].apply(_deve_ignorar_transacao)].copy()

    df = _garantir_colunas_finais(df)
    df = df.dropna(subset=["id_transacao"]).copy()
    return df


def _calcular_resumo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["categoria", "total", "percentual"])

    resumo = df.groupby("categoria", as_index=False)["valor"].sum().rename(columns={"valor": "total"})
    total = resumo["total"].sum()
    resumo["percentual"] = ((resumo["total"] / total) * 100).round(2) if total else 0.0
    return resumo.sort_values("total", ascending=False).reset_index(drop=True)


def _escrever_saida(df: pd.DataFrame, resumo: pd.DataFrame) -> tuple[int, int]:
    """
    Escreve saída em CSV local e tenta inserir em Google Sheets.
    
    Retorna tupla (inseridas_sheets, puladas_sheets).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_TRANSACOES_CSV, index=False, encoding="utf-8-sig")
    logger.info("Transações escritas em: %s", OUTPUT_TRANSACOES_CSV)
    
    resumo.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    logger.info("Resumo escrito em: %s", OUTPUT_CSV)
    
    # Tenta inserir em Google Sheets
    try:
        inseridas, puladas = inserir_transacoes_sheets(df)
        salvar_transacoes(df)
        for banco in sorted(set(df.get("banco", pd.Series(dtype=str)).astype(str).dropna().tolist())):
            registrar_banco(banco, origem="pipeline")
        return inseridas, puladas
    except Exception as exc:
        logger.warning("Falha ao inserir em Google Sheets: %s", exc)
        try:
            salvar_transacoes(df)
        except Exception as db_exc:
            logger.warning("Falha ao salvar transações no SQLite: %s", db_exc)
        return 0, 0


def run_pipeline(ano_referencia: int | None = None) -> None:
    init_repository()
    inicio = time.time()
    logger.info("=" * 70)
    logger.info("INICIANDO PIPELINE DE CONTROLE DE GASTOS")
    logger.info("=" * 70)

    # === LISTAR ARQUIVOS ===
    logger.info("\n[1/5] Listando arquivos disponíveis...")
    fontes = listar_faturas()
    logger.info("Encontrados %d arquivo(s) de fatura.", len(fontes))
    if fontes:
        for fonte in fontes:
            logger.info("  • %s (%s) [%s]", fonte.nome_arquivo, fonte.origem, fonte.banco)

    # === PROCESSAR ARQUIVOS ===
    logger.info("\n[2/5] Processando arquivos...")
    processados_ja = carregar_processados()
    novos_frames: list[pd.DataFrame] = []
    arquivos_processados = 0
    transacoes_extraidas = 0
    ignorados_por_dedup = 0

    for fonte in fontes:
        if fonte.identificador in processados_ja:
            logger.info("⊘ %s — já processado, pulando.", fonte.nome_arquivo)
            continue

        logger.info("▶ Processando: %s", fonte.nome_arquivo)
        try:
            texto_bruto = ler_texto_fatura(fonte)
        except Exception as exc:
            logger.warning("  ✗ Falha ao ler texto: %s", exc)
            texto_bruto = ""

        parser = _selecionar_parser(fonte, texto_bruto)
        try:
            df_parsed = parser(fonte.caminho_local, ano_referencia=ano_referencia)
        except Exception as exc:
            logger.warning("  ✗ Falha ao parsear com %s: %s", parser.__name__, exc)
            registrar_processado(fonte.identificador, fonte.nome_arquivo, fonte.origem)
            registrar_importacao(fonte.identificador, fonte.nome_arquivo, fonte.origem, "erro", str(exc))
            continue

        if df_parsed.empty:
            logger.info("  ⊘ Nenhuma transação extraída.")
            registrar_processado(fonte.identificador, fonte.nome_arquivo, fonte.origem)
            registrar_importacao(fonte.identificador, fonte.nome_arquivo, fonte.origem, "vazio", "nenhuma transacao extraida")
            continue

        df_normalizado = _normalizar_transacoes(
            df_parsed,
            origem=fonte.origem,
            nome_arquivo=fonte.nome_arquivo,
            banco=fonte.banco,
        )
        if df_normalizado.empty:
            logger.info("  ⊘ Todas as transações foram descartadas (inválidas).")
            registrar_processado(fonte.identificador, fonte.nome_arquivo, fonte.origem)
            registrar_importacao(fonte.identificador, fonte.nome_arquivo, fonte.origem, "descartado", "todas as transacoes invalidas")
            continue

        arquivos_processados += 1
        transacoes_extraidas += len(df_normalizado)
        novos_frames.append(df_normalizado)
        registrar_processado(fonte.identificador, fonte.nome_arquivo, fonte.origem)
        registrar_importacao(fonte.identificador, fonte.nome_arquivo, fonte.origem, "ok", f"{len(df_normalizado)} transacoes")
        logger.info("  ✓ %d transações extraídas com sucesso.", len(df_normalizado))

    logger.info("Processamento de arquivos concluído: %d arquivo(s) processado(s), %d transações extraídas.",
                arquivos_processados, transacoes_extraidas)

    # === LER GASTOS MANUAIS ===
    logger.info("\n[3/5] Lendo gastos manuais da aba '2026'...")
    df_manual = ler_gastos()
    if not df_manual.empty:
        logger.info("Lidos %d gastos manuais.", len(df_manual))
        df_manual = _normalizar_transacoes(
            df_manual,
            origem="google_sheets",
            nome_arquivo="google_sheets",
            banco="manual",
        )
        novos_frames.append(df_manual)
    else:
        logger.info("Nenhum gasto manual encontrado.")

    # === CONSOLIDAR ===
    logger.info("\n[4/5] Consolidando dados...")
    existentes = _carregar_existentes()

    if not existentes.empty:
        data_existente = pd.to_datetime(existentes["data"], errors="coerce")
        origem_google = existentes["origem"].astype(str).eq("google_sheets")
        fora_abril_2026 = origem_google & ((data_existente.dt.year != 2026) | (data_existente.dt.month != 4))
        removidas = int(fora_abril_2026.sum())
        if removidas:
            logger.info("Limpando %d transações antigas de Google Sheets fora de abril/2026.", removidas)
            existentes = existentes.loc[~fora_abril_2026].copy()

    logger.info("Transações já registradas localmente: %d", len(existentes))
    
    combinado = pd.concat([existentes] + novos_frames, ignore_index=True)
    if combinado.empty:
        combinado = pd.DataFrame(columns=COLUNAS_FINAIS)

    antes = len(combinado)
    combinado = combinado.drop_duplicates(subset=["id_transacao"], keep="last").reset_index(drop=True)
    ignorados_por_dedup = antes - len(combinado)
    logger.info("Duplicatas removidas: %d", ignorados_por_dedup)
    logger.info("Total de transações consolidadas: %d", len(combinado))

    # === RESUMO E SAÍDA ===
    logger.info("\n[5/5] Gerando resumo e escrevendo saída...")
    resumo = _calcular_resumo(combinado)
    inseridas_sheets, puladas_sheets = _escrever_saida(combinado, resumo)

    # === RELATÓRIO FINAL ===
    elapsed = time.time() - inicio
    logger.info("\n" + "=" * 70)
    logger.info("RESUMO DA EXECUÇÃO")
    logger.info("=" * 70)
    logger.info("Arquivos processados: %d", arquivos_processados)
    logger.info("Transações extraídas dos arquivos: %d", transacoes_extraidas)
    logger.info("Transações manuais incluídas: %d", len(df_manual) if not df_manual.empty else 0)
    logger.info("Duplicatas removidas: %d", ignorados_por_dedup)
    logger.info("Total consolidado: %d", len(combinado))
    logger.info("Inseridas em Google Sheets: %d", inseridas_sheets)
    logger.info("Já existentes no Sheets: %d", puladas_sheets)
    logger.info("Arquivos CSV gerados em: %s", OUTPUT_DIR)
    logger.info("Tempo total: %.2f segundos", elapsed)
    logger.info("=" * 70)

    if not resumo.empty:
        logger.info("\nResumo por categoria:")
        for _, row in resumo.iterrows():
            logger.info("  %s: R$ %.2f (%.1f%%)", row["categoria"], row["total"], row["percentual"])


def carregar_resumo_atual() -> pd.DataFrame:
    if not OUTPUT_CSV.exists():
        return pd.DataFrame(columns=["categoria", "total", "percentual"])
    try:
        return pd.read_csv(OUTPUT_CSV)
    except Exception:
        return pd.DataFrame(columns=["categoria", "total", "percentual"])
