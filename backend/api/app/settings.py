from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_name: str = "Website Analytics API"
    api_prefix: str = "/api"
    # TODO: 添加后端真实配置（如数据库/鉴权/第三方密钥）

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
