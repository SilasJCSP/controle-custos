from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ResumoFinanceiro:
    total: float
    compras: float
    pagamentos: float
    quantidade: int
    mes_referencia: str = ""


@dataclass
class MetaFinanceira:
    categoria: str
    valor_meta: float
    gasto_atual: float
    alerta_percentual: float = 0.8


@dataclass
class InsightFinanceiro:
    mensagem: str
    tipo: str = "info"


def para_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return dict(obj)