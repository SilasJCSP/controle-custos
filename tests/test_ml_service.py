from __future__ import annotations

from pathlib import Path

import pandas as pd

import ml.service as ml_service


def test_prever_categoria_sem_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_service, "MODELO_PATH", tmp_path / "modelo_categoria.pkl", raising=False)

    resultado = ml_service.prever_categoria("uber eats sao paulo")

    assert resultado["categoria"] == "Outros"
    assert resultado["fonte"] == "sem_modelo"


def test_treinar_modelo_com_dados_falsos(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_service, "MODELO_PATH", tmp_path / "modelo_categoria.pkl", raising=False)
    monkeypatch.setattr(
        ml_service,
        "buscar_transacoes",
        lambda: pd.DataFrame(
            [
                {"descricao": "ifood restaurante", "categoria": "Alimentação"},
                {"descricao": "uber viagem", "categoria": "Transporte"},
                {"descricao": "netflix assinatura", "categoria": "Serviços"},
                {"descricao": "ifood delivery", "categoria": "Alimentação"},
                {"descricao": "spotify premium", "categoria": "Serviços"},
                {"descricao": "mercado pão", "categoria": "Alimentação"},
                {"descricao": "uber eats", "categoria": "Alimentação"},
                {"descricao": "combustivel posto", "categoria": "Transporte"},
                {"descricao": "uber flash", "categoria": "Transporte"},
                {"descricao": "ifood almoço", "categoria": "Alimentação"},
            ]
        ),
        raising=False,
    )

    resultado = ml_service.treinar_modelo(min_amostras=5)

    assert resultado["treinado"] is True
    assert Path(ml_service.MODELO_PATH).exists()