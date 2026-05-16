from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    base_dir: Path = Field(default=Path(__file__).resolve().parents[1])
    output_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "output")
    cache_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "cache")
    log_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "logs")
    database_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "database")
    database_path: Path = Field(default=Path(__file__).resolve().parents[1] / "database" / "gastos.db")

    credentials_path: Path = Field(default=Path(__file__).resolve().parents[1] / "credenciais.json")
    oauth_client_secrets_path: Path = Field(default=Path(__file__).resolve().parents[1] / "google_oauth_client.json")
    oauth_token_path: Path = Field(default=Path(__file__).resolve().parents[1] / "output" / "google_oauth_token.json")

    gmail_cache_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "output" / "gmail_cache")
    drive_cache_dir: Path = Field(default=Path(__file__).resolve().parents[1] / "output" / "drive_cache")

    drive_folder_id: str = Field(default="")
    sheets_spreadsheet_id: str = Field(default="")
    sheets_name: str = Field(default="Controle de Gastos")
    sheets_data_tab: str = Field(default="Dados")
    sheets_control_tab: str = Field(default="processamento")
    auth_mode: str = Field(default="auto")

    gmail_sender_filter: str = Field(default="")
    gmail_subject_filter: str = Field(default="")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    settings = AppSettings()
    settings.base_dir = settings.base_dir.resolve()
    settings.output_dir = settings.output_dir.resolve()
    settings.cache_dir = settings.cache_dir.resolve()
    settings.log_dir = settings.log_dir.resolve()
    settings.database_dir = settings.database_dir.resolve()
    settings.database_path = settings.database_path.resolve()
    settings.credentials_path = settings.credentials_path.resolve()
    settings.oauth_client_secrets_path = settings.oauth_client_secrets_path.resolve()
    settings.oauth_token_path = settings.oauth_token_path.resolve()
    settings.gmail_cache_dir = settings.gmail_cache_dir.resolve()
    settings.drive_cache_dir = settings.drive_cache_dir.resolve()
    return settings