from __future__ import annotations

from app.parsers.nubank import NubankParser


def parse(caminho_pdf, ano_referencia: int | None = None):
    return NubankParser().parse(caminho_pdf, ano_referencia=ano_referencia)