from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pdfplumber

from config import DRIVE_CACHE_DIR, DRIVE_FOLDER_ID, PASTA_FATURAS, DRIVE_SCOPES
from data_source.google_utils import caminho_seguro, carregar_credenciais
from data_source.models import FaturaFonte


logger = logging.getLogger(__name__)
MANIFESTO_DRIVE = DRIVE_CACHE_DIR / "manifest.json"


def _gerar_id_local(caminho_pdf: Path) -> str:
    stat = caminho_pdf.stat()
    base = f"{caminho_pdf.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _carregar_manifesto() -> dict[str, str]:
    if not MANIFESTO_DRIVE.exists():
        return {}
    try:
        return json.loads(MANIFESTO_DRIVE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar_manifesto(manifesto: dict[str, str]) -> None:
    DRIVE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTO_DRIVE.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")


def _detectar_banco_por_nome(nome: str) -> str:
    base = nome.lower()
    if "santander" in base:
        return "santander"
    if "mercado" in base:
        return "mercado_pago"
    if "nubank" in base:
        return "nubank"
    if "itau" in base or "itaú" in base:
        return "itau"
    return "generico"


def _listar_faturas_locais() -> list[FaturaFonte]:
    if not PASTA_FATURAS.exists():
        return []

    fontes: list[FaturaFonte] = []
    for caminho_pdf in sorted(PASTA_FATURAS.glob("*.pdf")):
        fontes.append(
            FaturaFonte(
                identificador=_gerar_id_local(caminho_pdf),
                nome_arquivo=caminho_pdf.name,
                caminho_local=caminho_pdf,
                origem="local",
                banco=_detectar_banco_por_nome(caminho_pdf.name),
            )
        )
    return fontes


def _extrair_texto_pdf(caminho_pdf: Path) -> str:
    if not caminho_pdf.exists():
        return ""
    partes: list[str] = []
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                partes.append(pagina.extract_text() or "")
    except Exception as exc:
        logger.warning("Falha ao extrair texto de %s: %s", caminho_pdf.name, exc)
    return "\n".join(partes)


def _baixar_arquivo_drive(service, file_id: str, destino: Path) -> None:
    from googleapiclient.http import MediaIoBaseDownload
    import io

    request = service.files().get_media(fileId=file_id)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _listar_faturas_drive() -> list[FaturaFonte]:
    credenciais = carregar_credenciais(DRIVE_SCOPES)
    if credenciais is None:
        return []

    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        logger.warning("Google API client indisponível para Drive: %s", exc)
        return []

    service = build("drive", "v3", credentials=credenciais, cache_discovery=False)
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType='application/pdf' and trashed=false"
    pagina_token = None
    manifesto = _carregar_manifesto()
    fontes: list[FaturaFonte] = []

    while True:
        resposta = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, modifiedTime, mimeType, size)",
                pageToken=pagina_token,
                pageSize=100,
            )
            .execute()
        )
        for arquivo in resposta.get("files", []):
            file_id = arquivo["id"]
            nome = arquivo["name"]
            modified_time = arquivo.get("modifiedTime", "")
            safe_name = caminho_seguro(f"{file_id}_{nome}")
            destino = DRIVE_CACHE_DIR / safe_name

            if manifesto.get(file_id) != modified_time or not destino.exists():
                logger.info("Baixando PDF do Drive: %s", nome)
                _baixar_arquivo_drive(service, file_id, destino)
                manifesto[file_id] = modified_time

            fontes.append(
                FaturaFonte(
                    identificador=file_id,
                    nome_arquivo=nome,
                    caminho_local=destino,
                    origem="google_drive",
                    banco=_detectar_banco_por_nome(nome),
                    modified_time=modified_time,
                )
            )

        pagina_token = resposta.get("nextPageToken")
        if not pagina_token:
            break

    _salvar_manifesto(manifesto)
    return fontes


def listar_faturas() -> list[FaturaFonte]:
    """Lista faturas disponíveis. Prioriza Google Drive quando configurado, senão usa pasta local."""
    if DRIVE_FOLDER_ID:
        fontes = _listar_faturas_drive()
        if fontes:
            return fontes
        logger.info("Google Drive não disponível/sem itens; usando pasta local.")
    return _listar_faturas_locais()


def listar_pdfs() -> list[Path]:
    """Compatibilidade com código antigo: retorna apenas paths locais."""
    return [fonte.caminho_local for fonte in listar_faturas()]


def ler_texto_fatura(fonte: FaturaFonte) -> str:
    """Lê o texto bruto do PDF da fatura."""
    return _extrair_texto_pdf(fonte.caminho_local)
