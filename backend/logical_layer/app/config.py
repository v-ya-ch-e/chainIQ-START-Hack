from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ORGANISATIONAL_LAYER_URL: str = "http://organisational-layer:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
