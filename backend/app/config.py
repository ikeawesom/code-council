"""Settings loaded from environment / .env. Single source of truth for paths."""
from pathlib import Path

from pydantic_settings import BaseSettings

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    llm_provider: str = "claude_cli"
    claude_model: str = "opus"
    # A batched tagging prompt for a 100-clause contract genuinely takes minutes.
    claude_timeout: int = 600
    local_base_url: str = "http://localhost:11434"
    local_model: str = "qwen2.5:32b-instruct"
    offline: bool = False
    scrape_cron_hour: int = 7
    timezone: str = "Asia/Singapore"
    scheduler_enabled: bool = True
    scrape_lookback_days: int = 7
    # M3 retrieval: top-K candidate clauses per item, and the cost gate - an
    # item whose best hybrid score is below `retrieve_min_score` never reaches
    # the judge. The default is tuned in analysis/retrieve.py against the real
    # 5 Aug 2026 sitting so the planted demo item clears it on merit.
    retrieve_top_k: int = 5
    retrieve_min_score: float = 20.0
    retrieve_query_chars: int = 6000
    retrieve_query_terms: int = 40
    # Hard cap on judge calls per run, applied after the gate, best items first.
    analysis_max_items: int = 15

    vault_dir: Path = REPO_ROOT / "vault"
    inbox_dir: Path = REPO_ROOT / "data" / "inbox"
    fixtures_dir: Path = REPO_ROOT / "data" / "fixtures"
    llm_cache_dir: Path = REPO_ROOT / "data" / "llm_cache"
    db_path: Path = REPO_ROOT / "data" / "app.db"

    class Config:
        env_prefix = "CC_"
        env_file = ".env"


settings = Settings()
