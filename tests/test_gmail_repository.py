from __future__ import annotations

import importlib

import database.db as db_module
from repositories import sqlite_repository as repo


def test_salvar_e_buscar_email_processado(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "gastos.db", raising=False)
    importlib.reload(repo)

    repo.salvar_email_processado(
        "gmail-1",
        thread_id="thread-1",
        remetente="financeiro@exemplo.com",
        assunto="Fatura",
        mensagem_id="msg-1",
        arquivo_pdf="fatura.pdf",
        hash_conteudo="abc",
    )

    df = repo.buscar_emails_processados()

    assert len(df) == 1
    assert df.iloc[0]["gmail_id"] == "gmail-1"