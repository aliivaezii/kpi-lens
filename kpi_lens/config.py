"""
Central settings object — the only place that reads from environment variables.

Every other module imports `settings` from here. No module calls os.environ directly.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: SecretStr = Field(..., description="Claude API key")
    # claude-sonnet-4-6 gives the best cost/quality balance for structured analysis
    anthropic_model: str = Field(default="claude-sonnet-4-6")
    anthropic_max_tokens: int = Field(default=2048)
    anthropic_max_retries: int = Field(default=3)

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default=f"sqlite:///{PROJECT_ROOT / 'data' / 'kpi_lens.db'}"
    )

    # ── MCP Server ────────────────────────────────────────────────────────────
    mcp_transport: str = Field(default="stdio")
    mcp_port: int = Field(default=8080)

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    kpi_lens_env: str = Field(default="development")

    # ── Email (optional) ──────────────────────────────────────────────────────
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: SecretStr = Field(default=SecretStr(""))

    # ── Paths ─────────────────────────────────────────────────────────────────
    config_dir: Path = Field(default=PROJECT_ROOT / "config")
    exports_dir: Path = Field(default=PROJECT_ROOT / "data" / "exports")

    @property
    def is_production(self) -> bool:
        return self.kpi_lens_env == "production"


# Module-level singleton — import this everywhere.
# pydantic-settings populates required fields from the environment at runtime;
# mypy can't see that, so we suppress the false-positive [call-arg] here.
settings = Settings()  # type: ignore[call-arg]
