"""Compatibilidade com a configuração antiga; o canonical é app.settings."""

from __future__ import annotations

from app.settings import get_settings

_settings = get_settings()

BASE_DIR = _settings.base_dir
CREDENCIAIS_PATH = _settings.credentials_path
GOOGLE_CREDENTIALS_PATH = _settings.credentials_path
GOOGLE_OAUTH_CLIENT_SECRETS_PATH = _settings.oauth_client_secrets_path
PASTA_FATURAS = BASE_DIR / "dados" / "faturas"
OUTPUT_DIR = _settings.output_dir
LOG_DIR = _settings.log_dir
OUTPUT_CSV = OUTPUT_DIR / "gastos_consolidados.csv"
OUTPUT_TRANSACOES_CSV = OUTPUT_DIR / "transacoes_categorizadas.csv"
DRIVE_CACHE_DIR = _settings.drive_cache_dir
PROCESSED_REGISTRY_FILE = OUTPUT_DIR / "processed_files.json"
GOOGLE_OAUTH_TOKEN_PATH = _settings.oauth_token_path
DRIVE_FOLDER_ID = _settings.drive_folder_id
SPREADSHEET_ID = _settings.sheets_spreadsheet_id
GOOGLE_SHEETS_NAME = _settings.sheets_name
NOME_PLANILHA = _settings.sheets_name
NOME_ABA = _settings.sheets_data_tab
NOME_ABA_CONTROLE = _settings.sheets_control_tab
GOOGLE_AUTH_MODE = _settings.auth_mode
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SCOPES = DRIVE_SCOPES + SHEETS_SCOPES
