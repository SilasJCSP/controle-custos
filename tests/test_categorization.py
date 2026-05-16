from __future__ import annotations

from app.categorization.service import categorizar_com_score, memorizar_categoria


def test_categorization_with_score_and_memory():
    memorizar_categoria("99pizza", "Alimentação", 1.0)
    resultado = categorizar_com_score("Compra 99Pizza SP")

    assert resultado["categoria"] == "Alimentação"
    assert 0.0 <= float(resultado["confianca"]) <= 1.0


def test_categorization_fuzzy_match():
    resultado = categorizar_com_score("uber eats sao paulo")

    assert isinstance(resultado, dict)
    assert "categoria" in resultado
    assert "confianca" in resultado