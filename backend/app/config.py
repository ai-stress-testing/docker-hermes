"""Environment-driven configuration. No hardcoded values."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Base URL of the LM Studio OpenAI-compatible API, e.g. http://lmstudio:1234
    lmstudio_url: str = "http://localhost:1234"

    # Model name used when the incoming request does not specify one.
    default_model: str = "default"

    # Timeout (seconds) for outbound requests to LM Studio.
    request_timeout: float = 30.0

    # Standard python logging level name.
    log_level: str = "INFO"

    # Timeout (seconds) for the lightweight /ready check against LM Studio.
    # Deliberately short and independent of REQUEST_TIMEOUT.
    ready_check_timeout: float = 2.0

    # Maximum accepted request body size, in bytes. Requests larger than
    # this are rejected with 413 before the body is fully parsed.
    max_request_body_bytes: int = 2_000_000

    @property
    def lmstudio_base_url(self) -> str:
        return self.lmstudio_url.rstrip("/")


settings = Settings()
