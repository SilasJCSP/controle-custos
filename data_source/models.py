from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FaturaFonte:
    """Representa uma fatura disponível para processamento."""

    identificador: str
    nome_arquivo: str
    caminho_local: Path
    origem: str
    banco: str = "generico"
    modified_time: str = ""
