from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from config import GOOGLE_AUTH_MODE, GOOGLE_OAUTH_CLIENT_SECRETS_PATH, GOOGLE_OAUTH_TOKEN_PATH
from app.repositories.sqlite_repository import buscar_emails_processados, salvar_email_processado


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GmailArquivo:
    gmail_id: str
    thread_id: str
    remetente: str
    assunto: str
    mensagem_id: str
    arquivo_pdf: str
    path_local: Path


def _hash_bytes(conteudo: bytes) -> str:
    return hashlib.sha1(conteudo).hexdigest()


def _extrair_pdf_anexo(service, mensagem) -> list[GmailArquivo]:
    anexos: list[GmailArquivo] = []
    payload = mensagem.get("payload", {})
    parts = payload.get("parts", []) or []
    headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", []) or []}
    remetente = headers.get("from", "")
    assunto = headers.get("subject", "")
    mensagem_id = headers.get("message-id", "")
    gmail_id = mensagem.get("id", "")
    thread_id = mensagem.get("threadId", "")

    for part in parts:
        filename = part.get("filename", "") or ""
        body = part.get("body", {}) or {}
        mime_type = part.get("mimeType", "") or ""
        if not filename.lower().endswith(".pdf") and mime_type != "application/pdf":
            continue

        attachment_id = body.get("attachmentId")
        if not attachment_id:
            continue

        attachment = service.users().messages().attachments().get(
            userId="me",
            messageId=gmail_id,
            id=attachment_id,
        ).execute()
        data = attachment.get("data", "")
        conteudo = base64.urlsafe_b64decode(data.encode("utf-8"))
        hash_conteudo = _hash_bytes(conteudo)

        destino = Path("output") / "gmail_cache" / f"{gmail_id}_{filename}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)

        anexos.append(
            GmailArquivo(
                gmail_id=gmail_id,
                thread_id=thread_id,
                remetente=remetente,
                assunto=assunto,
                mensagem_id=mensagem_id,
                arquivo_pdf=filename,
                path_local=destino,
            )
        )
        salvar_email_processado(gmail_id, thread_id, remetente, assunto, mensagem_id, filename, hash_conteudo)

    return anexos


def _obter_servico_gmail():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except Exception as exc:
        logger.warning("Cliente Gmail indisponível: %s", exc)
        return None

    scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    try:
        creds = None
        if GOOGLE_OAUTH_TOKEN_PATH.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(GOOGLE_OAUTH_TOKEN_PATH), scopes=scopes)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            except Exception as exc:
                logger.warning("Falha ao carregar token Gmail salvo: %s", exc)
                creds = None

        if creds is None:
            if not GOOGLE_OAUTH_CLIENT_SECRETS_PATH.exists():
                logger.info("Client secrets OAuth não encontrados; Gmail não pode autenticar.")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_OAUTH_CLIENT_SECRETS_PATH), scopes=scopes)
            try:
                creds = flow.run_local_server(port=0, prompt="consent")
            except Exception:
                creds = flow.run_console()
            GOOGLE_OAUTH_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            GOOGLE_OAUTH_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as exc:
        logger.warning("Falha ao abrir serviço Gmail: %s", exc)
        return None


def importar_faturas_gmail(remetente_contendo: str = "", assunto_contendo: str = "") -> list[GmailArquivo]:
    servico = _obter_servico_gmail()
    if servico is None:
        return []

    query_parts = ["has:attachment filename:pdf"]
    if remetente_contendo:
        query_parts.append(f"from:({remetente_contendo})")
    if assunto_contendo:
        query_parts.append(f"subject:({assunto_contendo})")
    query = " ".join(query_parts)

    historico = buscar_emails_processados()
    processados = set(historico["gmail_id"].astype(str).tolist()) if not historico.empty else set()
    resposta = servico.users().messages().list(userId="me", q=query, maxResults=20).execute()
    mensagens = resposta.get("messages", []) or []
    novos_arquivos: list[GmailArquivo] = []

    for item in mensagens:
        gmail_id = item.get("id", "")
        if not gmail_id or gmail_id in processados:
            continue

        mensagem = servico.users().messages().get(userId="me", id=gmail_id, format="full").execute()
        novos_arquivos.extend(_extrair_pdf_anexo(servico, mensagem))

        try:
            servico.users().messages().modify(
                userId="me",
                id=gmail_id,
                body={"addLabelIds": ["Label_Processed"]},
            ).execute()
        except Exception:
            pass

    return novos_arquivos