"""
VTR-Agent: Configuration Management

Pydantic settings with environment variable support and validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App metadata
    APP_NAME: str = "VTR-Agent"
    APP_VERSION: str = "0.1.0"
    DEMO_MODE: bool = True
    ENVIRONMENT: str = "development"

    # Security
    JWT_SECRET_KEY: str = Field(default="demo-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES: int = 3600

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:////tmp/vtr_agent.db", description="SQLite database URL"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis (for rate limiting and caching)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8501",
        ]
    )

    # Security
    RATE_LIMIT: int = 100
    RATE_LIMIT_WINDOW: str = "1 minute"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024

    # Sandbox
    SANDBOX_TIMEOUT: int = 300
    SANDBOX_MEMORY_LIMIT: int = 4096
    SANDBOX_CPU_LIMIT: float = 2.0
    SANDBOX_BASE_IMAGE: str = "python:3.11-slim"

    # LLM & Web Search Providers
    LLM_PROVIDER: str = Field(default="groq")
    GROQ_API_KEY: Optional[str] = Field(default=None)
    TAVILY_API_KEY: Optional[str] = Field(default=None)
    LLM_MODEL: str = Field(default="llama-3.3-70b-versatile")
    LLM_TEMPERATURE: float = Field(default=0.2)
    LLM_MAX_TOKENS: int = Field(default=4096)

    # ML Model
    MODEL_PATH: str = Field(default="")
    MODEL_MAX_LENGTH: int = 2048
    MODEL_BATCH_SIZE: int = 8

    # Retrieval
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_CHUNK_SIZE: int = 800
    RETRIEVAL_OVERLAP: int = 100

    # Evidence
    EVIDENCE_MAX_CLAIMS: int = 100
    EVIDENCE_MAX_SOURCES: int = 50

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "vtr_agent.log"

    # Monitoring
    OTEL_SERVICE_NAME: str = "vtr-agent"
    OTEL_SERVICE_VERSION: str = "0.1.0"

    # File upload
    ALLOWED_EXTENSIONS: List[str] = [".txt", ".pdf", ".md", ".csv", ".docx"]

    # Approval workflows
    APPROVAL_REQUIRED_RISK_LEVELS: List[int] = [1, 2]
    APPROVAL_TIMEOUT: int = 3600

    @computed_field
    @property
    def DATABASE_FILE(self) -> Optional[str]:
        """Extract database filename for SQLite."""
        if self.DATABASE_URL.startswith("sqlite:///"):
            return self.DATABASE_URL.replace("sqlite:///", "")
        return None

    def ensure_dirs(self) -> None:
        """Create necessary directories for data storage."""
        data_dir = ROOT / "data"
        data_dir.mkdir(exist_ok=True)

        logs_dir = ROOT / "logs"
        logs_dir.mkdir(exist_ok=True)

        uploads_dir = ROOT / "uploads"
        uploads_dir.mkdir(exist_ok=True)

        sandboxes_dir = ROOT / "sandboxes"
        sandboxes_dir.mkdir(exist_ok=True)

        models_dir = ROOT / "models"
        models_dir.mkdir(exist_ok=True)

        evidence_dir = ROOT / "evidence"
        evidence_dir.mkdir(exist_ok=True)


# Create a singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Backward compatibility
settings = get_settings()
