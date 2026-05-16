from __future__ import annotations

from difflib import SequenceMatcher, get_close_matches
from pathlib import Path

import pandas as pd

from categorias_config import CATEGORIAS
from app.repositories.sqlite_repository import buscar_categorias, salvar_categoria_usuario
from utils.text import normalizar_descricao


BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_MEMORIA = BASE_DIR / "categorias_usuario.csv"

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
PALAVRAS_CATEGORIAS = {
    categoria: [normalizar_descricao(palavra) for palavra in palavras]
    for categoria, palavras in CATEGORIAS.items()
}
TODAS_PALAVRAS = [palavra for palavras in PALAVRAS_CATEGORIAS.values() for palavra in palavras]


def _carregar_memoria_compatibilidade() -> dict[str, tuple[str, float | None]]:
    memoria: dict[str, tuple[str, float | None]] = {}

    if ARQUIVO_MEMORIA.exists():
        try:
            df_memoria = pd.read_csv(ARQUIVO_MEMORIA)
            if {"descricao", "categoria"}.issubset(df_memoria.columns):
                for _, row in df_memoria.dropna().iterrows():
                    descricao = normalizar_descricao(str(row["descricao"]))
                    categoria = str(row["categoria"]).strip()
                    if descricao and categoria:
                        memoria[descricao] = (categoria, 1.0)
        except Exception:
            pass

    try:
        df_sqlite = buscar_categorias()
        if not df_sqlite.empty:
            for _, row in df_sqlite.dropna(subset=["descricao", "categoria"]).iterrows():
                descricao = normalizar_descricao(str(row["descricao"]))
                categoria = str(row["categoria"]).strip()
                confianca = float(row["confianca"]) if pd.notna(row.get("confianca")) else None
                if descricao and categoria:
                    memoria[descricao] = (categoria, confianca)
    except Exception:
        pass

    return memoria


MEMORIA_USUARIO = _carregar_memoria_compatibilidade()


def _score_similaridade(texto_a: str, texto_b: str) -> float:
    return SequenceMatcher(None, texto_a, texto_b).ratio()


def categorizar_com_score(descricao: str) -> dict[str, object]:
    descricao_norm = normalizar_descricao(descricao)
    if not descricao_norm:
        return {"categoria": "Outros", "confianca": 0.0}

    for descricao_memoria, (categoria, confianca) in MEMORIA_USUARIO.items():
        if descricao_memoria and descricao_memoria in descricao_norm:
            return {"categoria": categoria, "confianca": float(confianca or 1.0)}

    for categoria, palavras in PALAVRAS_CATEGORIAS.items():
        for palavra in palavras:
            if palavra and palavra in descricao_norm:
                return {"categoria": categoria, "confianca": 0.92}

    match = get_close_matches(descricao_norm, TODAS_PALAVRAS, n=1, cutoff=0.75)
    if match:
        palavra_encontrada = match[0]
        for categoria, palavras in PALAVRAS_CATEGORIAS.items():
            if palavra_encontrada in palavras:
                return {"categoria": categoria, "confianca": 0.80}

    melhor_categoria = "Outros"
    melhor_score = 0.0
    for categoria, palavras in PALAVRAS_CATEGORIAS.items():
        for palavra in palavras:
            score = _score_similaridade(descricao_norm, palavra)
            if score > melhor_score:
                melhor_score = score
                melhor_categoria = categoria

    if melhor_score >= 0.6:
        return {"categoria": melhor_categoria, "confianca": round(float(melhor_score), 2)}

    return {"categoria": "Outros", "confianca": 0.5}


def categorizar_texto(descricao: str) -> str:
    return str(categorizar_com_score(descricao)["categoria"])


def normalizar_categoria(categoria: str, descricao: str = "") -> str:
    texto = normalizar_descricao(categoria)
    if not texto:
        return categorizar_texto(descricao)

    if categoria in VALIDAS:
        return categoria

    if texto in ALIAS_CATEGORIAS:
        return ALIAS_CATEGORIAS[texto]

    if descricao:
        return categorizar_texto(descricao)

    return "Outros"


def memorizar_categoria(descricao: str, categoria: str, confianca: float | None = None) -> None:
    descricao_norm = normalizar_descricao(descricao)
    if not descricao_norm:
        return
    MEMORIA_USUARIO[descricao_norm] = (categoria, confianca)
    try:
        salvar_categoria_usuario(descricao_norm, categoria, confianca)
    except Exception:
        pass