from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "wa.db"


def _load_env_file() -> Path | None:
    """按优先级加载 .env 文件，返回实际加载的路径。"""

    candidates = [
        Path.cwd() / ".env",  # 当前工作目录
        Path(__file__).resolve().parents[2] / ".env",  # 项目 backend 根目录
    ]

    for path in candidates:
        if path.exists():
            load_dotenv(path, override=False)
            return path
    return None


_ENV_FILE = _load_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )

    project_name: str = "Website Analytics API"
    api_prefix: str = "/api"

    # 数据库 / 认证
    database_url: str = f"sqlite:///{_DEFAULT_DB_PATH}"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    admin_seed_username: str | None = None
    admin_seed_password: str | None = None

    # OpenAI / LLM 相关
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    agent_model: str = "gpt-5.1-codex-mini"

    # Playwright / 代理
    playwright_proxy_server: str | None = None

    # 巡检与截图
    inspect_max_menu_entries: int = 3
    llm_snapshot: bool = True
    llm_snapshot_fullpage: bool = True

    # 任务调度
    task_runner_enabled: bool = True
    task_runner_interval_seconds: int = 5
    task_runner_headless: bool = True
    task_runner_timeout_seconds: int = 600
    task_runner_max_concurrent: int = 1


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
