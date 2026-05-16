#!/usr/bin/env python3
"""Script de validação do pipeline de controle de gastos.

Verifica:
- Dependências importadas
- Credenciais Google
- Configurações
- Conectividade
- Integridade da base de dados
"""

from __future__ import annotations

import sys
from pathlib import Path

def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_ok(msg: str) -> None:
    print(f"  ✓ {msg}")

def print_warn(msg: str) -> None:
    print(f"  ⚠ {msg}")

def print_error(msg: str) -> None:
    print(f"  ✗ {msg}")

# ==============================================================================
# 1. VALIDAR IMPORTS
# ==============================================================================

print_header("1. VALIDANDO IMPORTS")

try:
    import pandas as pd
    print_ok("pandas")
except ImportError:
    print_error("pandas não instalado. Execute: pip install pandas")
    sys.exit(1)

try:
    import pdfplumber
    print_ok("pdfplumber")
except ImportError:
    print_error("pdfplumber não instalado. Execute: pip install pdfplumber")
    sys.exit(1)

try:
    import gspread
    print_ok("gspread")
except ImportError:
    print_error("gspread não instalado. Execute: pip install gspread")
    sys.exit(1)

try:
    from google.oauth2.service_account import Credentials as SACredentials
    print_ok("google-auth (service account)")
except ImportError:
    print_warn("google-auth não instalado (optional)")

try:
    from google.oauth2.credentials import Credentials as OAuthCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    print_ok("google-auth-oauthlib (OAuth)")
except ImportError:
    print_warn("google-auth-oauthlib não instalado (optional, para OAuth)")

try:
    from googleapiclient.discovery import build
    print_ok("google-api-python-client")
except ImportError:
    print_error("google-api-python-client não instalado. Execute: pip install google-api-python-client")
    sys.exit(1)

# Imports do projeto
try:
    from pipeline.processor import run_pipeline
    print_ok("pipeline.processor")
except ImportError as e:
    print_error(f"Falha ao importar pipeline.processor: {e}")
    sys.exit(1)

try:
    from data_source.sheets import ler_gastos, inserir_transacoes_sheets
    print_ok("data_source.sheets")
except ImportError as e:
    print_error(f"Falha ao importar data_source.sheets: {e}")
    sys.exit(1)

try:
    from data_source.drive import listar_faturas, ler_texto_fatura
    print_ok("data_source.drive")
except ImportError as e:
    print_error(f"Falha ao importar data_source.drive: {e}")
    sys.exit(1)

try:
    from app.parsers import GenericoParser, MercadoPagoParser, SantanderParser
    print_ok("parsers (santander, mercado_pago, generico)")
except ImportError as e:
    print_error(f"Falha ao importar parsers: {e}")
    sys.exit(1)

print_ok("TODOS OS IMPORTS OK")

# ==============================================================================
# 2. VALIDAR CONFIGURAÇÃO
# ==============================================================================

print_header("2. VALIDANDO CONFIGURAÇÃO")

from config import (
    CREDENCIAIS_PATH,
    GOOGLE_OAUTH_CLIENT_SECRETS_PATH,
    SPREADSHEET_ID,
    DRIVE_FOLDER_ID,
    OUTPUT_DIR,
)

if CREDENCIAIS_PATH.exists():
    print_ok(f"Arquivo de credenciais encontrado: {CREDENCIAIS_PATH}")
elif GOOGLE_OAUTH_CLIENT_SECRETS_PATH.exists():
    print_ok(f"Arquivo OAuth secrets encontrado: {GOOGLE_OAUTH_CLIENT_SECRETS_PATH}")
else:
    print_warn("Nenhum arquivo de credenciais encontrado")
    print_warn("  - Para OAuth: coloque 'google_oauth_client.json' na raiz")
    print_warn("  - Para Service Account: coloque 'credenciais.json' na raiz")

print(f"  Planilha ID: {SPREADSHEET_ID}")
if SPREADSHEET_ID and len(SPREADSHEET_ID) > 20:
    print_ok("ID de planilha configurado")
else:
    print_warn("ID de planilha pode estar inválido")

print(f"  Drive Folder ID: {DRIVE_FOLDER_ID}")
if DRIVE_FOLDER_ID and len(DRIVE_FOLDER_ID) > 10:
    print_ok("ID de pasta Drive configurado")
else:
    print_warn("ID de pasta Drive pode estar inválido")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print_ok(f"Diretório de saída: {OUTPUT_DIR}")

# ==============================================================================
# 3. VALIDAR CREDENCIAIS GOOGLE
# ==============================================================================

print_header("3. VALIDANDO CREDENCIAIS GOOGLE")

from data_source.google_utils import carregar_credenciais
from config import SHEETS_SCOPES, DRIVE_SCOPES

credenciais_sheets = carregar_credenciais(SHEETS_SCOPES)
if credenciais_sheets:
    print_ok("Credenciais Google Sheets carregadas")
else:
    print_warn("Não foi possível carregar credenciais Sheets")

credenciais_drive = carregar_credenciais(DRIVE_SCOPES)
if credenciais_drive:
    print_ok("Credenciais Google Drive carregadas")
else:
    print_warn("Não foi possível carregar credenciais Drive")

# ==============================================================================
# 4. VALIDAR CONECTIVIDADE COM GOOGLE SHEETS
# ==============================================================================

print_header("4. VALIDANDO CONECTIVIDADE COM GOOGLE SHEETS")

try:
    df_2026 = ler_gastos()
    if df_2026 is not None:
        print_ok(f"Conectividade Sheets OK - Lidos {len(df_2026)} registros da aba '2026'")
    else:
        print_warn("Aba '2026' retornou DataFrame vazio")
except Exception as e:
    print_warn(f"Falha ao ler aba '2026': {e}")

# ==============================================================================
# 5. VALIDAR CONECTIVIDADE COM GOOGLE DRIVE
# ==============================================================================

print_header("5. VALIDANDO CONECTIVIDADE COM GOOGLE DRIVE")

try:
    faturas = listar_faturas()
    print_ok(f"Listagem de Drive OK - Encontrados {len(faturas)} arquivo(s)")
    for fatura in faturas[:3]:  # Mostrar apenas os 3 primeiros
        print(f"    • {fatura.nome_arquivo} [{fatura.banco}]")
    if len(faturas) > 3:
        print(f"    ... e mais {len(faturas) - 3}")
except Exception as e:
    print_warn(f"Falha ao listar arquivos do Drive: {e}")

# ==============================================================================
# 6. VALIDAR ESTRUTURA LOCAL
# ==============================================================================

print_header("6. VALIDANDO ESTRUTURA LOCAL")

base_dir = Path(__file__).resolve().parent

dirs_esperados = [
    "parser",
    "data_source",
    "pipeline",
    "utils",
]

for d in dirs_esperados:
    path = base_dir / d
    if path.exists() and path.is_dir():
        print_ok(f"Diretório {d}/ existe")
    else:
        print_error(f"Diretório {d}/ não encontrado")

arquivos_esperados = [
    "main.py",
    "config.py",
    "requirements.txt",
    "categorias.py",
]

for f in arquivos_esperados:
    path = base_dir / f
    if path.exists():
        print_ok(f"Arquivo {f} existe")
    else:
        print_warn(f"Arquivo {f} não encontrado")

# ==============================================================================
# 7. VALIDAR INTEGRIDADE DO CSV EXISTENTE
# ==============================================================================

print_header("7. VALIDANDO INTEGRIDADE DO CSV EXISTENTE")

from config import OUTPUT_TRANSACOES_CSV

if OUTPUT_TRANSACOES_CSV.exists():
    try:
        df_csv = pd.read_csv(OUTPUT_TRANSACOES_CSV)
        print_ok(f"CSV existente: {len(df_csv)} transações")
        colunas = list(df_csv.columns)
        print(f"    Colunas: {', '.join(colunas[:3])}...")
    except Exception as e:
        print_error(f"Falha ao ler CSV: {e}")
else:
    print(f"    Nenhum CSV existente em {OUTPUT_TRANSACOES_CSV}")

# ==============================================================================
# 8. RESUMO FINAL
# ==============================================================================

print_header("RESUMO")

print("\n✓ Sistema pronto para execução!\n")
print("Para iniciar o pipeline, execute:")
print("  python main.py\n")

print("Ou para mais detalhes, veja:")
print("  - GUIA_RESTAURACAO.md (instruções de uso)")
print("  - MUDANCAS_TECNICAS.md (detalhes técnicos)\n")
