from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOG_LEVEL: str = "info"

    REDIS_URL: str
    REDIS_CLUSTER_MODE: bool = False
    REDIS_KEY_PREFIX: str = "louvre"
