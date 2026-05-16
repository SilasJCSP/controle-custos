from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.parsers.nubank import NubankParser
from app.parsers.santander import SantanderParser
from app.core.parsing import ParseContext, extrair_transacoes_basicas


def test_extrair_transacoes_basicas():
    linhas = ["01/05 Uber 42,50", "02/05 Mercado 10,00"]
    df = extrair_transacoes_basicas(linhas, ParseContext(arquivo_fatura="teste.pdf", banco="generico", ano_referencia=2026))

    assert len(df) == 2
    assert list(df["descricao"]) == ["Uber", "Mercado"]


def test_nubank_parser_parse_text():
    parser = NubankParser()
    df = parser.parse_text("01/05 Uber 42,50", Path("nubank.pdf"), ano_referencia=2026)

    assert len(df) == 1
    assert df.iloc[0]["banco"] == "nubank"


def test_santander_parser_monkeypatched(monkeypatch, tmp_path):
    import app.parsers.santander as santander_mod

    def fake_extrair(path, ano_referencia):
        return pd.DataFrame(
            [{"data": pd.Timestamp("2026-05-01"), "descricao": "Uber", "valor": 42.5}]
        )

    monkeypatch.setattr(santander_mod, "extrair_transacoes_santander", fake_extrair)
    arquivo = tmp_path / "santander.pdf"
    arquivo.write_text("x", encoding="utf-8")

    df = SantanderParser().parse(arquivo, ano_referencia=2026)

    assert len(df) == 1
    assert df.iloc[0]["banco"] == "santander"