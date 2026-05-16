from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd

from database.db import connection, init_db


logger = logging.getLogger(__name__)


def init_repository() -> None:
    init_db()


def salvar_transacoes(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0

    init_db()
    registros = df.copy()
    if "id_transacao" not in registros.columns:
        raise ValueError("DataFrame deve conter id_transacao")

    colunas = [
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
    faltantes = [col for col in colunas if col not in registros.columns]
    for coluna in faltantes:
        registros[coluna] = "" if coluna != "valor" else 0.0

    registros = registros[colunas].copy()
    registros["data"] = pd.to_datetime(registros["data"], errors="coerce").dt.strftime("%Y-%m-%d")
    registros["valor"] = pd.to_numeric(registros["valor"], errors="coerce")
    registros = registros.dropna(subset=["id_transacao", "data", "descricao", "valor"]).copy()

    if registros.empty:
        return 0

    with connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO transacoes (
                id_transacao, data, descricao, valor, categoria, banco, arquivo_fatura, origem, tipo_lancamento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [tuple(row) for row in registros.itertuples(index=False, name=None)],
        )

    return int(len(registros))


def buscar_transacoes(limit: int | None = None) -> pd.DataFrame:
    init_db()
    query = "SELECT id_transacao, data, descricao, valor, categoria, banco, arquivo_fatura, origem, tipo_lancamento FROM transacoes ORDER BY data DESC, descricao ASC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    with connection() as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return pd.DataFrame(columns=["id_transacao", "data", "descricao", "valor", "categoria", "banco", "arquivo_fatura", "origem", "tipo_lancamento"])
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df


def salvar_categoria_usuario(descricao: str, categoria: str, confianca: float | None = None) -> None:
    init_db()
    descricao = str(descricao).strip()
    categoria = str(categoria).strip()
    if not descricao or not categoria:
        return

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO categorias_usuario (descricao, categoria, confianca)
            VALUES (?, ?, ?)
            ON CONFLICT(descricao) DO UPDATE SET
                categoria = excluded.categoria,
                confianca = excluded.confianca,
                created_at = CURRENT_TIMESTAMP
            """,
            (descricao, categoria, confianca),
        )


def buscar_categorias() -> pd.DataFrame:
    init_db()
    with connection() as conn:
        df = pd.read_sql_query("SELECT descricao, categoria, confianca, created_at FROM categorias_usuario ORDER BY descricao ASC", conn)

    if df.empty:
        return pd.DataFrame(columns=["descricao", "categoria", "confianca", "created_at"])
    return df


def registrar_importacao(identificador: str, nome_arquivo: str, origem: str, status: str, mensagem: str = "") -> None:
    init_db()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO importacoes (identificador, nome_arquivo, origem, status, mensagem)
            VALUES (?, ?, ?, ?, ?)
            """,
            (identificador, nome_arquivo, origem, status, mensagem),
        )


def registrar_banco(nome: str, origem: str = "") -> None:
    init_db()
    nome = str(nome).strip()
    if not nome:
        return

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO bancos (nome, origem)
            VALUES (?, ?)
            ON CONFLICT(nome) DO UPDATE SET origem = excluded.origem
            """,
            (nome, origem),
        )


def salvar_meta_financeira(categoria: str, valor_meta: float, periodo: str = "mensal", alerta_percentual: float = 0.8) -> None:
    init_db()
    categoria = str(categoria).strip()
    if not categoria:
        return

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO metas_financeiras (categoria, valor_meta, periodo, alerta_percentual)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(categoria, periodo) DO UPDATE SET
                valor_meta = excluded.valor_meta,
                alerta_percentual = excluded.alerta_percentual,
                created_at = CURRENT_TIMESTAMP
            """,
            (categoria, float(valor_meta), periodo, float(alerta_percentual)),
        )


def buscar_metas_financeiras() -> pd.DataFrame:
    init_db()
    with connection() as conn:
        df = pd.read_sql_query("SELECT categoria, valor_meta, periodo, alerta_percentual, created_at FROM metas_financeiras ORDER BY categoria ASC", conn)

    if df.empty:
        return pd.DataFrame(columns=["categoria", "valor_meta", "periodo", "alerta_percentual", "created_at"])
    return df


def salvar_email_processado(
    gmail_id: str,
    thread_id: str = "",
    remetente: str = "",
    assunto: str = "",
    mensagem_id: str = "",
    arquivo_pdf: str = "",
    hash_conteudo: str = "",
) -> None:
    init_db()
    gmail_id = str(gmail_id).strip()
    if not gmail_id:
        return

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO emails_processados (
                gmail_id, thread_id, remetente, assunto, mensagem_id, arquivo_pdf, hash_conteudo
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(gmail_id) DO UPDATE SET
                thread_id = excluded.thread_id,
                remetente = excluded.remetente,
                assunto = excluded.assunto,
                mensagem_id = excluded.mensagem_id,
                arquivo_pdf = excluded.arquivo_pdf,
                hash_conteudo = excluded.hash_conteudo,
                processado_em = CURRENT_TIMESTAMP
            """,
            (gmail_id, thread_id, remetente, assunto, mensagem_id, arquivo_pdf, hash_conteudo),
        )


def buscar_emails_processados(limit: int | None = None) -> pd.DataFrame:
    init_db()
    query = "SELECT gmail_id, thread_id, remetente, assunto, mensagem_id, arquivo_pdf, hash_conteudo, processado_em FROM emails_processados ORDER BY processado_em DESC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    with connection() as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return pd.DataFrame(columns=["gmail_id", "thread_id", "remetente", "assunto", "mensagem_id", "arquivo_pdf", "hash_conteudo", "processado_em"])
    return df