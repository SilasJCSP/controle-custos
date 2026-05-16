"""Dashboard de gastos pessoais em Streamlit."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from app.repositories.sqlite_repository import buscar_metas_financeiras, buscar_transacoes, salvar_meta_financeira
from app.services.export_service import exportar_excel, exportar_pdf
from app.services.insights_service import comparar_meses, detectar_recorrentes, gerar_insights, prever_fechamento, resumo_mensal, top_despesas


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_TRANSACOES = BASE_DIR / "output" / "transacoes_categorizadas.csv"
ARQUIVO_RESUMO = BASE_DIR / "output" / "gastos_consolidados.csv"


@st.cache_data(ttl=60)
def carregar_transacoes() -> pd.DataFrame:
    try:
        df_sqlite = buscar_transacoes()
        if not df_sqlite.empty:
            return df_sqlite
    except Exception:
        pass

    if not ARQUIVO_TRANSACOES.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(ARQUIVO_TRANSACOES)
    except Exception:
        return pd.DataFrame()

    colunas_esperadas = ["data", "descricao", "valor", "categoria"]
    if any(col not in df.columns for col in colunas_esperadas):
        return pd.DataFrame()

    if "banco" not in df.columns:
        df["banco"] = "nao_identificado"
    if "tipo_lancamento" not in df.columns:
        df["tipo_lancamento"] = "compra"
    if "origem" not in df.columns:
        df["origem"] = ""

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["data", "valor", "categoria", "descricao"]).copy()

    return df


@st.cache_data(ttl=60)
def carregar_resumo() -> pd.DataFrame:
    if not ARQUIVO_RESUMO.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(ARQUIVO_RESUMO)
    except Exception:
        return pd.DataFrame()

    if not {"categoria", "total", "percentual"}.issubset(df.columns):
        return pd.DataFrame()

    return df


def _aplicar_estilo_mobile() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #0b1020 0%, #111827 100%); color: #f3f4f6; }
        div[data-testid="stSidebar"] { background: #0f172a; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1200px; }
        .stMetric { background: rgba(255,255,255,0.04); padding: 12px; border-radius: 16px; }
        @media (max-width: 768px) {
            .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
            .stMetric { padding: 10px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filtros")

    busca = st.sidebar.text_input("Buscar descrição", value="")

    bancos = ["Todos"] + sorted(df["banco"].astype(str).unique().tolist())
    categorias = ["Todas"] + sorted(df["categoria"].astype(str).unique().tolist())
    tipos = ["Todos"] + sorted(df["tipo_lancamento"].astype(str).unique().tolist())

    banco_sel = st.sidebar.selectbox("Banco", bancos, index=0)
    categoria_sel = st.sidebar.selectbox("Categoria", categorias, index=0)
    tipo_sel = st.sidebar.selectbox("Tipo de lançamento", tipos, index=0)

    data_min = df["data"].min().date()
    data_max = df["data"].max().date()
    periodo = st.sidebar.date_input(
        "Período",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
    )

    filtrado = df.copy()

    if banco_sel != "Todos":
        filtrado = filtrado[filtrado["banco"] == banco_sel]
    if categoria_sel != "Todas":
        filtrado = filtrado[filtrado["categoria"] == categoria_sel]
    if tipo_sel != "Todos":
        filtrado = filtrado[filtrado["tipo_lancamento"] == tipo_sel]

    if busca.strip():
        termo = busca.strip().lower()
        filtrado = filtrado[filtrado["descricao"].astype(str).str.lower().str.contains(termo, na=False)]

    if isinstance(periodo, tuple) and len(periodo) == 2:
        inicio, fim = periodo
        filtrado = filtrado[(filtrado["data"].dt.date >= inicio) & (filtrado["data"].dt.date <= fim)]

    return filtrado


def render_kpis(df: pd.DataFrame) -> None:
    total = float(df["valor"].sum()) if not df.empty else 0.0
    compras = float(df[df["tipo_lancamento"] == "compra"]["valor"].sum()) if not df.empty else 0.0
    pagamentos = float(df[df["tipo_lancamento"] == "pagamento"]["valor"].sum()) if not df.empty else 0.0
    qtd = int(len(df))
    media = float(df["valor"].mean()) if not df.empty else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total no período", f"R$ {total:,.2f}")
    col2.metric("Compras", f"R$ {compras:,.2f}")
    col3.metric("Pagamentos", f"R$ {pagamentos:,.2f}")
    col4.metric("Qtd. lançamentos", f"{qtd}")
    col5.metric("Ticket médio", f"R$ {media:,.2f}")


def render_charts(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("Sem dados para os filtros selecionados.")
        return

    resumo_mensal = (
        df.assign(mes=df["data"].dt.to_period("M").dt.to_timestamp())
        .groupby("mes", as_index=False)["valor"].sum()
        .sort_values("mes")
    )

    st.subheader("Distribuição por categoria")
    por_categoria = df.groupby("categoria", as_index=False)["valor"].sum().sort_values("valor", ascending=False)
    if not por_categoria.empty:
        pie_data = por_categoria.copy()
        pie_data["label"] = pie_data["categoria"].astype(str)
        pie_chart = (
            alt.Chart(pie_data)
            .mark_arc()
            .encode(
                theta=alt.Theta("valor:Q", stack=True),
                color=alt.Color("label:N", title="Categoria"),
                tooltip=["label:N", "valor:Q"],
            )
            .properties(height=280)
        )
        st.altair_chart(pie_chart, use_container_width=True)
    st.bar_chart(por_categoria.set_index("categoria"))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Distribuição por banco")
        por_banco = df.groupby("banco", as_index=False)["valor"].sum().sort_values("valor", ascending=False)
        st.bar_chart(por_banco.set_index("banco"))

    with col2:
        st.subheader("Distribuição por tipo")
        por_tipo = df.groupby("tipo_lancamento", as_index=False)["valor"].sum().sort_values("valor", ascending=False)
        st.bar_chart(por_tipo.set_index("tipo_lancamento"))

    st.subheader("Resumo mensal")
    st.line_chart(resumo_mensal.set_index("mes")["valor"])

    st.subheader("Heatmap de gastos")
    mapa = df.copy()
    mapa["mes"] = mapa["data"].dt.month
    mapa["dia"] = mapa["data"].dt.day
    heatmap = mapa.pivot_table(index="dia", columns="mes", values="valor", aggfunc="sum", fill_value=0)
    if not heatmap.empty:
        heatmap_long = heatmap.reset_index().melt(id_vars="dia", var_name="mes", value_name="valor")
        heatmap_chart = (
            alt.Chart(heatmap_long)
            .mark_rect()
            .encode(
                x=alt.X("mes:O", title="Mês"),
                y=alt.Y("dia:O", title="Dia"),
                color=alt.Color("valor:Q", scale=alt.Scale(scheme="blues"), title="R$"),
                tooltip=["mes", "dia", "valor"],
            )
            .properties(height=300)
        )
        st.altair_chart(heatmap_chart, use_container_width=True)

    st.subheader("Categorias mais usadas")
    categorias_mais_usadas = df.groupby("categoria", as_index=False).size().sort_values("size", ascending=False).head(10)
    st.bar_chart(categorias_mais_usadas.set_index("categoria"))

    st.subheader("Top descrições por valor")
    top_descricoes = (
        df.groupby("descricao", as_index=False)["valor"].sum()
        .sort_values("valor", ascending=False)
        .head(15)
    )
    st.dataframe(top_descricoes, use_container_width=True)


def render_metas(df: pd.DataFrame) -> None:
    st.subheader("Metas financeiras")
    metas = buscar_metas_financeiras()
    if metas.empty:
        st.info("Nenhuma meta cadastrada ainda.")
    else:
        for _, meta in metas.iterrows():
            categoria = str(meta["categoria"])
            valor_meta = float(meta["valor_meta"])
            gasto_categoria = float(df[df["categoria"] == categoria]["valor"].sum()) if not df.empty else 0.0
            percentual = min(1.0, gasto_categoria / valor_meta) if valor_meta else 0.0
            st.write(f"{categoria}: R$ {gasto_categoria:,.2f} de R$ {valor_meta:,.2f}")
            st.progress(percentual)
            if percentual >= float(meta.get("alerta_percentual", 0.8)):
                st.warning(f"Atenção: {categoria} já consumiu {percentual * 100:.0f}% da meta.")

    with st.expander("Adicionar ou atualizar meta"):
        categoria_meta = st.text_input("Categoria da meta")
        valor_meta = st.number_input("Valor da meta", min_value=0.0, step=50.0)
        alerta = st.slider("Alerta em % da meta", min_value=50, max_value=100, value=80) / 100
        if st.button("Salvar meta"):
            salvar_meta_financeira(categoria_meta, valor_meta, "mensal", alerta)
            st.success("Meta salva com sucesso.")


def render_insights(df: pd.DataFrame) -> None:
    st.subheader("Insights automáticos")
    for insight in gerar_insights(df):
        st.info(insight)

    comparacao = comparar_meses(df)
    if "variacao_percentual" in comparacao:
        delta = comparacao["variacao_percentual"]
        st.metric("Variação mês a mês", f"{delta:+.2f}%")

    previsao = prever_fechamento(df)
    if "previsao" in previsao:
        st.metric("Previsão de fechamento", f"R$ {previsao['previsao']:,.2f}")

    recorrentes = detectar_recorrentes(df)
    if not recorrentes.empty:
        st.write("Gastos recorrentes detectados")
        st.dataframe(recorrentes.head(10), use_container_width=True)


def render_tabela(df: pd.DataFrame) -> None:
    st.subheader("Transações filtradas")
    exibir = df.sort_values(["data", "valor"], ascending=[False, False]).copy()
    exibir["data"] = exibir["data"].dt.strftime("%Y-%m-%d")
    editavel = st.data_editor(exibir, use_container_width=True, num_rows="dynamic")

    csv = editavel.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Baixar transações filtradas (CSV)", data=csv, file_name="transacoes_filtradas.csv", mime="text/csv")

    buffer_excel = BytesIO()
    with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
        editavel.to_excel(writer, index=False, sheet_name="Transacoes")
    st.download_button(
        "Baixar transações filtradas (Excel)",
        data=buffer_excel.getvalue(),
        file_name="transacoes_filtradas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def render_exportacoes(df: pd.DataFrame) -> None:
    st.subheader("Exportação avançada")
    col1, col2 = st.columns(2)
    with col1:
        caminho_excel = exportar_excel(df, BASE_DIR / "output" / "relatorio_mensal.xlsx")
        st.caption(f"Excel gerado em {caminho_excel.name}")
    with col2:
        caminho_pdf = exportar_pdf(df, BASE_DIR / "output" / "relatorio_mensal.pdf")
        st.caption(f"PDF gerado em {caminho_pdf.name}")


def main() -> None:
    st.set_page_config(page_title="Dashboard de Gastos", layout="wide")
    _aplicar_estilo_mobile()
    st.title("📊 Dashboard de Gastos Pessoais")
    st.caption("Dados lidos do SQLite com fallback para CSV local.")

    df_transacoes = carregar_transacoes()
    if df_transacoes.empty:
        st.error("Dados de transações não encontrados. Execute `python main.py` antes.")
        st.stop()

    resumo = carregar_resumo()
    if not resumo.empty:
        st.caption("Resumo consolidado atual disponível em output/gastos_consolidados.csv")

    df_filtrado = aplicar_filtros(df_transacoes)

    aba_resumo, aba_graficos, aba_metas, aba_insights, aba_corrigir = st.tabs(
        ["Resumo", "Gráficos", "Metas", "Insights", "Tabela"]
    )

    with aba_resumo:
        render_kpis(df_filtrado)
        st.divider()
        render_exportacoes(df_filtrado)

    with aba_graficos:
        render_charts(df_filtrado)

    with aba_metas:
        render_metas(df_filtrado)

    with aba_insights:
        render_insights(df_filtrado)

    with aba_corrigir:
        render_tabela(df_filtrado)


if __name__ == "__main__":
    main()
