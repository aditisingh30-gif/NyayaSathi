import os
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    APP_NAME: str = "Indian Legal & Policy Information Assistant"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Storage Directories (Always absolute, rooted at project ROOT_DIR)
    DATA_DIR: Path = ROOT_DIR / "data"
    RAW_DOCS_DIR: Path = ROOT_DIR / "data" / "raw_documents"
    PROCESSED_DIR: Path = ROOT_DIR / "data" / "processed"
    VECTOR_STORE_DIR: Path = ROOT_DIR / "data" / "vector_store"

    @field_validator("DATA_DIR", "RAW_DOCS_DIR", "PROCESSED_DIR", "VECTOR_STORE_DIR", mode="before")
    def resolve_path(cls, v):
        if isinstance(v, (str, Path)):
            p = Path(v)
            if not p.is_absolute():
                # Resolve relative to ROOT_DIR
                if str(p).startswith(".."):
                    # Strip leading .. if specified relative to backend/
                    parts = list(p.parts)
                    while parts and parts[0] == "..":
                        parts.pop(0)
                    return ROOT_DIR.joinpath(*parts)
                return ROOT_DIR / p
            return p
        return v

    # Embeddings & Vector DB
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHROMA_COLLECTION_NAME: str = "indian_legal_documents"

    # LLM Providers
    DEFAULT_LLM_PROVIDER: str = "gemini"  # 'gemini', 'openai', 'ollama'
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
for directory in [
    settings.DATA_DIR,
    settings.RAW_DOCS_DIR,
    settings.PROCESSED_DIR,
    settings.VECTOR_STORE_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
