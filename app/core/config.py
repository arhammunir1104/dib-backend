# app/core/config.py
import os
import certifi
from pydantic_settings import BaseSettings
from typing import Optional

# Ensure SSL certificates work on Windows
os.environ["SSL_CERT_FILE"] = certifi.where()

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "DIB Circular AI"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database (MySQL via aiomysql)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "dib_circular_ai"
    DATABASE_URL: Optional[str] = None

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # LLM Provider
    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: str = ""                          # ← no default key – must be set in .env
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_TEMPERATURE: float = 0.0

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Storage
    UPLOAD_DIR: str = "./storage/uploads"
    TEMP_DIR: str = "./storage/temp"
    GENERATED_DIR: str = "./storage/generated"
    CACHE_DIR: str = "./storage/cache"
    TEMPLATE_DIR: str = "./templates"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()