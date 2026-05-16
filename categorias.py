"""Categorização inteligente de despesas.

Estratégia em camadas:
1) Memória do usuário (CSV local)
2) Regras determinísticas por palavras-chave
3) Similaridade textual (fuzzy)
4) Fallback para "Outros"
"""

from __future__ import annotations

from pathlib import Path
from difflib import get_close_matches
import pandas as pd

from app.categorization.service import categorizar_com_score, memorizar_categoria, normalizar_categoria as normalizar_categoria_servico
from categorias_config import CATEGORIAS
from utils.text import normalizar_descricao


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_MEMORIA = BASE_DIR / "categorias_usuario.csv"


def carregar_memoria() -> dict[str, str]:
    """Carrega memória local de categorização do usuário.

    Estrutura esperada do CSV: descricao,categoria
    """
    if not ARQUIVO_MEMORIA.exists():
        return {}

    try:
        df_memoria = pd.read_csv(ARQUIVO_MEMORIA)
    except Exception:
        return {}

    colunas = {col.lower().strip(): col for col in df_memoria.columns}
    if "descricao" not in colunas or "categoria" not in colunas:
        return {}

    descricao_col = colunas["descricao"]
    categoria_col = colunas["categoria"]

    df_memoria = df_memoria[[descricao_col, categoria_col]].dropna()
    memoria: dict[str, str] = {}

    for _, linha in df_memoria.iterrows():
        descricao = normalizar_descricao(str(linha[descricao_col]))
        categoria = str(linha[categoria_col]).strip()
        if descricao and categoria:
            memoria[descricao] = categoria

    return memoria


MEMORIA_USUARIO = carregar_memoria()

ALIAS_CATEGORIAS = {
    "supermercado": "Alimentação",
    "transporte": "Transporte/Auto",
    "assinaturas": "Serviços/Streaming",
    "compras": "Compras/Lojas",
    "faturas": "Outros Serviços",
    "carro": "Transporte/Auto",
    "custos ap": "Outros Serviços",
    "servicos": "Outros Serviços",
    "serviços": "Outros Serviços",
}

VALIDAS = set(CATEGORIAS.keys())

# construir mapa de palavras-chave por categoria (normalizado)
PALAVRAS_CATEGORIAS = {
    categoria: [normalizar_descricao(palavra) for palavra in palavras]
    for categoria, palavras in CATEGORIAS.items()
}

TODAS_PALAVRAS = [
    palavra
    for palavras in PALAVRAS_CATEGORIAS.values()
    for palavra in palavras
]


def categorizar(descricao: str) -> str:
    """Retorna categoria com base em memória e palavras-chave configuráveis.

    Prioriza matching por 'contains' usando versão normalizada da descrição.
    """
    return str(categorizar_com_score(descricao)["categoria"])


def normalizar_categoria(categoria: str, descricao: str = "") -> str:
    return normalizar_categoria_servico(categoria, descricao=descricao)


def categorizar_com_confianca(descricao: str) -> dict[str, object]:
    return categorizar_com_score(descricao)


def memorizar_categoria_local(descricao: str, categoria: str, confianca: float | None = None) -> None:
    memorizar_categoria(descricao, categoria, confianca)
