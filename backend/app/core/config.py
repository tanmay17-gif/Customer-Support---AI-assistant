"""
Application configuration — reads from .env file.
All path settings are resolved to absolute paths at startup using PROJECT_ROOT.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import pathlib

# Project root = CS_Assistant/ (2 levels above backend/app/core/)
# config.py is at: backend/app/core/config.py
# parent×1=core, ×2=app, ×3=backend, ×4=CS_Assistant
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    # ── LLM — Gemini is primary ─────────────────────────────────────────────
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-1.5-flash"
    BRAND_NAME: str = "SupportAI"
    BRAND_LOGO_URL: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_2: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # ── Telegram Admin Bot ──────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: str = ""  # Optional: restrict to one admin

    # ── Gmail (IMAP) ────────────────────────────────────────────────────────
    GMAIL_ADDRESS: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # ── Paths (resolved to absolute below) ──────────────────────────────────
    DATABASE_URL: str = ""
    CHROMA_PERSIST_DIR: str = ""
    POLICY_DOC_PATH: str = ""
    INVOICES_DIR: str = ""
    LOGS_DIR: str = ""

    # ── Server ───────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    DEBUG: bool = True

    class Config:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    data = _PROJECT_ROOT / "data"
    # Override with absolute paths so they work regardless of CWD
    if not s.DATABASE_URL:
        s.DATABASE_URL = f"sqlite:///{data / 'cs_assistant.db'}"
    if not s.CHROMA_PERSIST_DIR:
        s.CHROMA_PERSIST_DIR = str(data / "chroma_db")
    if not s.POLICY_DOC_PATH:
        s.POLICY_DOC_PATH = str(data / "policy" / "refund_policy.txt")
    if not s.INVOICES_DIR:
        s.INVOICES_DIR = str(data / "invoices")
    if not s.LOGS_DIR:
        s.LOGS_DIR = str(data / "logs")

    # Always resolve to absolute regardless of what .env says
    s.CHROMA_PERSIST_DIR = str((_PROJECT_ROOT / s.CHROMA_PERSIST_DIR.lstrip("./")).resolve()
                               if not pathlib.Path(s.CHROMA_PERSIST_DIR).is_absolute()
                               else pathlib.Path(s.CHROMA_PERSIST_DIR))
    s.POLICY_DOC_PATH = str((_PROJECT_ROOT / s.POLICY_DOC_PATH.lstrip("./")).resolve()
                            if not pathlib.Path(s.POLICY_DOC_PATH).is_absolute()
                            else pathlib.Path(s.POLICY_DOC_PATH))
    s.INVOICES_DIR = str((_PROJECT_ROOT / s.INVOICES_DIR.lstrip("./")).resolve()
                         if not pathlib.Path(s.INVOICES_DIR).is_absolute()
                         else pathlib.Path(s.INVOICES_DIR))
    return s


settings = get_settings()
PROJECT_ROOT = _PROJECT_ROOT
