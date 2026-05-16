"""Pipeline principal do projeto de controle de gastos pessoais.

Executa o fluxo completo:
1. Busca faturas no Google Drive
2. Processa PDFs (Santander, Mercado Pago, genérico)
3. Lê dados manuais da aba "2026"
4. Consolida tudo em base única
5. Insere em TRANSACOES_CONSOLIDADAS no Google Sheets
6. Gera CSVs locais para backup/análise
"""

from __future__ import annotations

import logging
from utils.logging_setup import setup_logging


def main() -> int:
    setup_logging()
    logger = logging.getLogger(__name__)

    from pipeline.processor import run_pipeline

    try:
        run_pipeline()
        return 0
    except Exception:
        logger.exception("Falha inesperada na execução do pipeline")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
