from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Sequence, Tuple

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import (
    CREDENCIAIS_PATH,
    GOOGLE_AUTH_MODE,
    GOOGLE_OAUTH_CLIENT_SECRETS_PATH,
    GOOGLE_OAUTH_TOKEN_PATH,
)


logger = logging.getLogger(__name__)


def credenciais_existentes() -> bool:
    return CREDENCIAIS_PATH.exists() or GOOGLE_OAUTH_CLIENT_SECRETS_PATH.exists()


def _carregar_token_salvo(scopes: Tuple[str, ...]) -> OAuthCredentials | None:
    if not GOOGLE_OAUTH_TOKEN_PATH.exists():
        return None
    try:
        return OAuthCredentials.from_authorized_user_file(str(GOOGLE_OAUTH_TOKEN_PATH), scopes=list(scopes))
    except Exception as exc:
        logger.warning("Falha ao carregar token OAuth salvo: %s", exc)
        return None


def _salvar_token_salvo(credentials: OAuthCredentials) -> None:
    GOOGLE_OAUTH_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOOGLE_OAUTH_TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")


def _carregar_credenciais_oauth(scopes: Tuple[str, ...]) -> OAuthCredentials | None:
    credentials = _carregar_token_salvo(scopes)
    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _salvar_token_salvo(credentials)
            return credentials
        except RefreshError as exc:
            logger.warning("Falha ao renovar token OAuth: %s", exc)
        except Exception as exc:
            logger.warning("Falha inesperada ao renovar token OAuth: %s", exc)

    if not GOOGLE_OAUTH_CLIENT_SECRETS_PATH.exists():
        logger.info(
            "Arquivo de client secrets OAuth não encontrado em %s",
            GOOGLE_OAUTH_CLIENT_SECRETS_PATH,
        )
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_OAUTH_CLIENT_SECRETS_PATH), scopes=list(scopes))
        try:
            credentials = flow.run_local_server(port=0, prompt="consent")
        except Exception:
            credentials = flow.run_console()
        _salvar_token_salvo(credentials)
        return credentials
    except Exception as exc:
        logger.warning("Falha no fluxo OAuth de usuário: %s", exc)
        return None


def _carregar_credenciais_service_account(scopes: Tuple[str, ...]) -> ServiceAccountCredentials | None:
    if not CREDENCIAIS_PATH.exists():
        logger.info("Credenciais de service account não encontradas em %s", CREDENCIAIS_PATH)
        return None

    try:
        return ServiceAccountCredentials.from_service_account_file(str(CREDENCIAIS_PATH), scopes=list(scopes))
    except Exception as exc:
        logger.warning("Falha ao carregar credenciais de service account: %s", exc)
        return None


@lru_cache(maxsize=8)
def _carregar_credenciais_cached(scopes_tuple: Tuple[str, ...]):
    """Carrega credenciais Google priorizando OAuth de usuário."""
    modo = GOOGLE_AUTH_MODE or "oauth"

    if modo == "service_account":
        credenciais = _carregar_credenciais_service_account(scopes_tuple)
        if credenciais is not None:
            return credenciais

    if modo == "auto":
        credenciais = _carregar_credenciais_service_account(scopes_tuple)
        if credenciais is not None:
            return credenciais

        credenciais = _carregar_credenciais_oauth(scopes_tuple)
        if credenciais is not None:
            return credenciais

    if modo in {"oauth", "user", "installed_app"}:
        credenciais = _carregar_credenciais_oauth(scopes_tuple)
        if credenciais is not None:
            return credenciais

    return None


def carregar_credenciais(scopes: Sequence[str]):
    return _carregar_credenciais_cached(tuple(scopes))


def caminho_seguro(nome: str) -> str:
    texto = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in nome)
    return texto.strip("._") or "arquivo.pdf"
