from __future__ import annotations

import importlib

import pandas as pd

import database.db as db_module
from app.repositories import sqlite_repository as repo


def test_salvar_e_buscar_transacoes(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "gastos.db", raising=False)
    importlib.reload(repo)

    df = pd.DataFrame(
        [
            {
                "id_transacao": "abc123",
                "data": "2026-05-01",
                "descricao": "Uber",
                "valor": 42.5,
                "categoria": "Transporte",
                "banco": "nubank",
                "arquivo_fatura": "teste.pdf",
                "origem": "fatura_pdf",
                "tipo_lancamento": "compra",
            }
        ]
    )

    assert repo.salvar_transacoes(df) == 1
    resultado = repo.buscar_transacoes()

    assert len(resultado) == 1
    assert resultado.iloc[0]["descricao"] == "Uber"
    assert resultado.iloc[0]["banco"] == "nubank"


def test_salvar_e_buscar_categorias(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "gastos.db", raising=False)
    importlib.reload(repo)

    repo.salvar_categoria_usuario("ifood", "Alimentação", 0.95)
    df = repo.buscar_categorias()

    assert len(df) == 1
    assert df.iloc[0]["categoria"] == "Alimentação"