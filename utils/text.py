from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd


def normalizar_descricao(texto: str) -> str:
    if texto is None:
        return ""
    valor = str(texto).lower().strip()
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(char for char in valor if not unicodedata.combining(char))
    # remove caracteres especiais mantendo letras, numeros e espaços
    valor = re.sub(r"[^a-z0-9\s]", " ", valor)
    valor = re.sub(r"\s+", " ", valor)
    return valor.strip()


def gerar_id_transacao(data: pd.Timestamp | str, valor: float | str, descricao: str) -> str:
    """Gera um identificador SHA1 baseado em data+valor+descricao normalizada."""
    partes = []
    if isinstance(data, pd.Timestamp):
        partes.append(str(data.date()))
    else:
        partes.append(str(data))
    partes.append(str(float(valor)))
    partes.append(normalizar_descricao(descricao))
    base = "|".join(partes)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def classificar_tipo_lancamento(descricao: str, valor: float) -> str:
    texto = normalizar_descricao(descricao)

    if valor < 0 or any(palavra in texto for palavra in ("pagamento", "estorno", "credito", "crédito")):
        return "pagamento"
    if any(palavra in texto for palavra in ("anuidade", "juros", "iof", "tarifa")):
        return "tarifa"
    if "ajuste" in texto:
        return "ajuste"
    if any(palavra in texto for palavra in ("credito", "crédito")) and valor > 0:
        return "pagamento"
    return "compra"
