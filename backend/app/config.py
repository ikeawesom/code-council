"""Settings loaded from environment / .env. Single source of truth for paths."""
from pathlib import Path

from pydantic_settings import BaseSettings

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    llm_provider: str = "claude_cli"
    claude_model: str = "opus"
    claude_timeout: int = 120
    local_base_url: str = "http://localhost:11434"
    local_model: str = "qwen2.5:32b-instruct"
    offline: bool = False
    scrape_cron_hour: int = 7
    timezone: str = "Asia/Singapore"

    vault_dir: Path = REPO_ROOT / "vault"
    inbox_dir: Path = REPO_ROOT / "data" / "inbox"
    fixtures_dir: Path = REPO_ROOT / "data" / "fixtures"
    llm_cache_dir: Path = REPO_ROOT / "data" / "llm_cache"
    db_path: Path = REPO_ROOT / "data" / "app.db"

    class Config:
        env_prefix = "LEX_"
        env_file = ".env"


settings = Settings()
