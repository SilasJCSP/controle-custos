from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "gastos.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transacoes (
    id_transacao TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    categoria TEXT NOT NULL,
    banco TEXT NOT NULL,
    arquivo_fatura TEXT NOT NULL,
    origem TEXT NOT NULL,
    tipo_lancamento TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categorias_usuario (
    descricao TEXT PRIMARY KEY,
    categoria TEXT NOT NULL,
    confianca REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS importacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT NOT NULL,
    hash_arquivo TEXT NOT NULL,
    banco TEXT NOT NULL,
    data_importacao TEXT DEFAULT CURRENT_TIMESTAMP,
    qtd_transacoes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    erro TEXT,
    UNIQUE(hash_arquivo, banco)
);

CREATE TABLE IF NOT EXISTS emails_processados (
    gmail_id TEXT PRIMARY KEY,
    thread_id TEXT,
    remetente TEXT,
    assunto TEXT,
    mensagem_id TEXT,
    arquivo_pdf TEXT,
    hash_conteudo TEXT,
    processado_em TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bancos (
    nome TEXT PRIMARY KEY,
    origem TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metas_financeiras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    valor_meta REAL NOT NULL,
    periodo TEXT NOT NULL DEFAULT 'mensal',
    alerta_percentual REAL DEFAULT 0.8,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(categoria, periodo)
);

CREATE INDEX IF NOT EXISTS idx_transacoes_data ON transacoes (data);
CREATE INDEX IF NOT EXISTS idx_transacoes_categoria ON transacoes (categoria);
CREATE INDEX IF NOT EXISTS idx_importacoes_hash_arquivo ON importacoes (hash_arquivo);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA_SQL)