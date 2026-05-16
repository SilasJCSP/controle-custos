from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def exportar_csv(df: pd.DataFrame, destino: str | Path) -> Path:
    caminho = Path(destino)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False, encoding="utf-8-sig")
    return caminho


def exportar_excel(df: pd.DataFrame, destino: str | Path) -> Path:
    caminho = Path(destino)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(caminho) as writer:
        df.to_excel(writer, index=False, sheet_name="Transacoes")
    return caminho


def exportar_pdf(df: pd.DataFrame, destino: str | Path, titulo: str = "Relatório Mensal") -> Path:
    caminho = Path(destino)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, altura - 40, titulo)
    pdf.setFont("Helvetica", 10)
    y = altura - 70
    pdf.drawString(40, y, f"Total de lançamentos: {len(df)}")
    y -= 20

    for _, row in df.head(25).iterrows():
        linha = f"{row.get('data', '')} | {row.get('descricao', '')} | R$ {row.get('valor', 0):.2f} | {row.get('categoria', '')}"
        pdf.drawString(40, y, linha[:110])
        y -= 14
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = altura - 40

    pdf.save()
    caminho.write_bytes(buffer.getvalue())
    return caminho