"""Interface Streamlit para revisão e correção de categorias."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.categorization.service import memorizar_categoria
from categorias_config import CATEGORIAS


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_DADOS = BASE_DIR / "output" / "transacoes_categorizadas.csv"
ARQUIVO_MEMORIA = BASE_DIR / "categorias_usuario.csv"


@st.cache_data
def carregar_dados() -> pd.DataFrame:
    """Carrega transações categorizadas geradas pelo pipeline."""
    if not ARQUIVO_DADOS.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(ARQUIVO_DADOS)
    except Exception:
        return pd.DataFrame()

    colunas_necessarias = ["data", "descricao", "valor", "categoria"]
    if any(col not in df.columns for col in colunas_necessarias):
        return pd.DataFrame()

    if "banco" not in df.columns:
        df["banco"] = "nao_identificado"
    if "arquivo_fatura" not in df.columns:
        df["arquivo_fatura"] = ""
    if "origem" not in df.columns:
        df["origem"] = ""
    if "tipo_lancamento" not in df.columns:
        df["tipo_lancamento"] = "compra"

    return df[colunas_necessarias + ["banco", "arquivo_fatura", "origem", "tipo_lancamento"]].copy()


def carregar_memoria() -> pd.DataFrame:
    """Carrega histórico de correções de categoria do usuário."""
    if not ARQUIVO_MEMORIA.exists():
        return pd.DataFrame(columns=["descricao", "categoria"])

    try:
        df = pd.read_csv(ARQUIVO_MEMORIA)
    except Exception:
        return pd.DataFrame(columns=["descricao", "categoria"])

    if "descricao" not in df.columns or "categoria" not in df.columns:
        return pd.DataFrame(columns=["descricao", "categoria"])

    return df[["descricao", "categoria"]].copy()


def salvar_memoria(df_memoria: pd.DataFrame) -> None:
    """Persiste memória de categorias em CSV."""
    df_saida = df_memoria[["descricao", "categoria"]].dropna().copy()
    df_saida["descricao"] = df_saida["descricao"].astype(str).str.strip()
    df_saida["categoria"] = df_saida["categoria"].astype(str).str.strip()
    df_saida = df_saida[(df_saida["descricao"] != "") & (df_saida["categoria"] != "")]
    df_saida = df_saida.drop_duplicates(subset=["descricao"], keep="last")
    df_saida.to_csv(ARQUIVO_MEMORIA, index=False, encoding="utf-8-sig")


st.set_page_config(page_title="Correção de Categorias", layout="wide")
st.title("💰 Correção de Categorias de Gastos")

st.caption("Dica: rode primeiro `python main.py` para atualizar o arquivo de transações.")

df = carregar_dados()
if df.empty:
    st.error("Arquivo de transações não encontrado ou inválido. Execute o pipeline primeiro.")
    st.stop()

categorias_disponiveis = list(CATEGORIAS.keys()) + ["Outros"]

col_a, col_b, col_c, col_d, col_e = st.columns(5)
with col_a:
    mostrar_somente_outros = st.checkbox("Mostrar somente 'Outros'", value=False)
with col_b:
    agrupar_descricoes = st.checkbox("Mostrar descrições únicas", value=True)
with col_c:
    ordenar_valor = st.checkbox("Ordenar por maior valor", value=True)
with col_d:
    bancos_disponiveis = ["Todos"] + sorted(df["banco"].dropna().astype(str).unique().tolist())
    filtro_banco = st.selectbox("Filtrar banco", bancos_disponiveis, index=0)
with col_e:
    tipos_disponiveis = ["Todos"] + sorted(df["tipo_lancamento"].dropna().astype(str).unique().tolist())
    filtro_tipo = st.selectbox("Filtrar tipo", tipos_disponiveis, index=0)

base = df.copy()
if filtro_banco != "Todos":
    base = base[base["banco"] == filtro_banco]
if filtro_tipo != "Todos":
    base = base[base["tipo_lancamento"] == filtro_tipo]
if mostrar_somente_outros:
    base = base[base["categoria"] == "Outros"]
if agrupar_descricoes:
    base = base.drop_duplicates(subset=["descricao"], keep="first")
if ordenar_valor:
    base = base.sort_values("valor", ascending=False)

if base.empty:
    st.warning("Nenhum registro disponível com os filtros selecionados.")
    st.stop()

st.write("### Ajuste suas categorias")

if "ajustes_massa" not in st.session_state:
    st.session_state["ajustes_massa"] = {}

descricoes_disponiveis = sorted(base["descricao"].astype(str).unique().tolist())
col_m1, col_m2, col_m3 = st.columns([4, 3, 2])
with col_m1:
    descricao_alvo = st.selectbox(
        "Descrição para aplicar em massa",
        descricoes_disponiveis,
        key="descricao_alvo_massa",
    )
with col_m2:
    categoria_alvo = st.selectbox(
        "Nova categoria",
        categorias_disponiveis,
        key="categoria_alvo_massa",
    )
with col_m3:
    st.write("")
    st.write("")
    if st.button("Aplicar para todos iguais", key="btn_aplicar_massa"):
        st.session_state["ajustes_massa"][descricao_alvo] = categoria_alvo
        st.success(f"Categoria '{categoria_alvo}' aplicada para '{descricao_alvo}'.")

edicoes: list[dict[str, str]] = []
for i, row in base.reset_index(drop=True).iterrows():
    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 5, 2, 3])

    with col1:
        st.write(str(row["data"]))

    with col2:
        st.write(str(row["banco"]))

    with col3:
        st.write(str(row["tipo_lancamento"]))

    with col4:
        st.write(str(row["descricao"]))

    with col5:
        st.write(f"R$ {float(row['valor']):.2f}")

    with col6:
        descricao_linha = str(row["descricao"])
        categoria_atual = st.session_state["ajustes_massa"].get(
            descricao_linha,
            str(row["categoria"]),
        )
        indice = (
            categorias_disponiveis.index(categoria_atual)
            if categoria_atual in categorias_disponiveis
            else categorias_disponiveis.index("Outros")
        )
        nova_categoria = st.selectbox(
            f"Categoria {i}",
            categorias_disponiveis,
            index=indice,
            key=f"cat_{i}",
            label_visibility="collapsed",
        )

    edicoes.append({"descricao": str(row["descricao"]), "categoria": nova_categoria})

if st.button("💾 Salvar correções", type="primary"):
    memoria_atual = carregar_memoria()
    novas_regras = pd.DataFrame(edicoes)

    memoria_atualizada = pd.concat([memoria_atual, novas_regras], ignore_index=True)
    salvar_memoria(memoria_atualizada)
    for _, row in novas_regras.dropna().iterrows():
        memorizar_categoria(str(row["descricao"]), str(row["categoria"]), confianca=1.0)

    st.success("Correções salvas em categorias_usuario.csv com sucesso!")
    st.info("Execute novamente `python main.py` para recalcular categorias e resumo.")
