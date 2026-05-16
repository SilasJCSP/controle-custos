from __future__ import annotations

import hashlib
from pathlib import Path

from repositories.sqlite_repository import buscar_emails_processados, registrar_importacao as registrar_importacao_sqlite


def hash_arquivo(caminho: str | Path) -> str:
    caminho = Path(caminho)
    if not caminho.exists():
        return ""
    stat = caminho.stat()
    base = f"{caminho.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def arquivo_ja_processado(hash_arquivo_pdf: str) -> bool:
    if not hash_arquivo_pdf:
        return False
    historico = buscar_emails_processados()
    if historico.empty or "hash_conteudo" not in historico.columns:
        return False
    return hash_arquivo_pdf in set(historico["hash_conteudo"].astype(str).tolist())


def registrar_importacao(*, identificador: str, nome_arquivo: str, origem: str, status: str, mensagem: str = "") -> None:
    registrar_importacao_sqlite(identificador, nome_arquivo, origem, status, mensagem)