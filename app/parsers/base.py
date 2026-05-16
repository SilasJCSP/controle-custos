from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from app.core.parsing import ParseContext, detectar_banco_por_texto, extrair_texto_pdf, normalizar_dataframe_parsado
from validators.dataframe_validator import validar_schema_dataframe


class BaseParser(ABC):
    banco: str = "generico"

    @abstractmethod
    def parse(self, caminho_pdf: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        raise NotImplementedError()

    def parse_text(self, texto: str, arquivo: Path, ano_referencia: int | None = None) -> pd.DataFrame:
        raise NotImplementedError()

    def validar(self, df: pd.DataFrame) -> pd.DataFrame:
        return validar_schema_dataframe(df, ["data", "descricao", "valor", "categoria", "banco", "arquivo_fatura"])


def detectar_banco(texto: str, caminho_pdf: Path) -> str:
    return detectar_banco_por_texto(texto, caminho_pdf)


def validar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    return validar_schema_dataframe(df, ["data", "descricao", "valor", "categoria", "banco", "arquivo_fatura"])


def parse_texto_generico(texto: str, arquivo: Path, banco: str, ano_referencia: int | None = None) -> pd.DataFrame:
    from app.core.parsing import extrair_transacoes_basicas

    contexto = ParseContext(arquivo_fatura=arquivo.name, banco=banco, ano_referencia=ano_referencia)
    df = extrair_transacoes_basicas(texto.splitlines(), contexto)
    return normalizar_dataframe_parsado(df, banco=banco, arquivo_fatura=arquivo.name)