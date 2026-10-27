import os
from dotenv import load_dotenv

# Load environment variables from .env in project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Base externa para chamadas à Evolution API
EVOLUTION_URL = os.getenv("EVOLUTION_URL", "").rstrip("/")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN", "")

# Configurações de banco de dados MySQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Google Sheets
GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "false").strip().lower() == "true"
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
GOOGLE_SHEETS_WORKSHEET = os.getenv("GOOGLE_SHEETS_WORKSHEET", "Dados").strip() or "Dados"
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "").strip()
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()

# Planilha de lojas (mapeamento loja -> estado)
GOOGLE_SHEETS_LOJA_ID = os.getenv("GOOGLE_SHEETS_LOJA_ID", "").strip()
GOOGLE_SHEETS_LOJA_WORKSHEET = os.getenv("GOOGLE_SHEETS_LOJA_WORKSHEET", "").strip()
GOOGLE_SHEETS_LOJA_PRIVATE_KEY = os.getenv("GOOGLE_SHEETS_LOJA_PRIVATE_KEY", "")
GOOGLE_SHEETS_LOJA_SERVICE_ACCOUNT = os.getenv("GOOGLE_SHEETS_LOJA_SERVICE_ACCOUNT", "").strip()

# FeriadosAPI (feriados nacionais e estaduais)
FERIADOS_API_KEY = os.getenv("FERIADOS_API_KEY", "").strip()

# Redis (cache diário de feriados e planilha de lojas); vazio = cache em memória
REDIS_URL = os.getenv("REDIS_URL", "").strip()
