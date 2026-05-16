from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from categorias import categorizar
from pipeline.processor import carregar_resumo_atual
from utils.text import classificar_tipo_lancamento, gerar_id_transacao, normalizar_descricao


def main() -> None:
    descricao = "  Uber   Eats! São Paulo  "
    normalizada = normalizar_descricao(descricao)
    assert normalizada == "uber eats sao paulo", normalizada

    hash_1 = gerar_id_transacao(pd.Timestamp("2026-05-01"), 42.5, descricao)
    hash_2 = gerar_id_transacao(pd.Timestamp("2026-05-01"), 42.5, descricao)
    assert hash_1 == hash_2

    categoria = categorizar("Compra no iFood SP")
    assert categoria in {"Alimentação", "Outros"}

    tipo = classificar_tipo_lancamento("Pagamento da fatura", -120.0)
    assert tipo == "pagamento"

    resumo = carregar_resumo_atual()
    assert isinstance(resumo, pd.DataFrame)

    print("SMOKE_OK")
    print({"normalizada": normalizada, "categoria": categoria, "tipo": tipo, "hash": hash_1[:12]})


if __name__ == "__main__":
    main()
