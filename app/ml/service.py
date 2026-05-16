from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd

from app.repositories.sqlite_repository import buscar_transacoes
from utils.text import normalizar_descricao


BASE_DIR = Path(__file__).resolve().parents[2]
MODELO_PATH = BASE_DIR / "ml" / "modelo_categoria.pkl"


def modelo_disponivel() -> bool:
    return MODELO_PATH.exists()


def _carregar_modelo():
    if not MODELO_PATH.exists():
        return None
    with MODELO_PATH.open("rb") as handle:
        return pickle.load(handle)


def treinar_modelo(min_amostras: int = 10) -> dict[str, object]:
    df = buscar_transacoes()
    if df.empty or "descricao" not in df.columns or "categoria" not in df.columns:
        return {"treinado": False, "motivo": "sem dados"}

    base = df.copy()
    base["descricao"] = base["descricao"].astype(str).apply(normalizar_descricao)
    base = base[base["categoria"].astype(str).str.strip().ne("Outros")]
    base = base[base["descricao"].astype(str).str.len() > 2]

    if len(base) < min_amostras:
        return {"treinado": False, "motivo": "amostras insuficientes", "amostras": int(len(base))}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except Exception as exc:
        return {"treinado": False, "motivo": f"sklearn indisponivel: {exc}"}

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), analyzer="word")),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )
    pipeline.fit(base["descricao"], base["categoria"])

    MODELO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MODELO_PATH.open("wb") as handle:
        pickle.dump(pipeline, handle)

    return {"treinado": True, "amostras": int(len(base)), "categorias": int(base["categoria"].nunique())}


def prever_categoria(descricao: str) -> dict[str, object]:
    descricao_norm = normalizar_descricao(descricao)
    if not descricao_norm:
        return {"categoria": "Outros", "confianca": 0.0, "fonte": "vazia"}

    modelo = _carregar_modelo()
    if modelo is None:
        return {"categoria": "Outros", "confianca": 0.0, "fonte": "sem_modelo"}

    try:
        categoria = modelo.predict([descricao_norm])[0]
        confianca = 0.5
        if hasattr(modelo, "predict_proba"):
            probabilidades = modelo.predict_proba([descricao_norm])[0]
            confianca = float(max(probabilidades))
        return {"categoria": str(categoria), "confianca": round(confianca, 2), "fonte": "ml"}
    except Exception:
        return {"categoria": "Outros", "confianca": 0.0, "fonte": "erro"}