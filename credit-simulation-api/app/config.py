from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    postgres_user: str = Field(min_length=1)
    postgres_password: SecretStr = Field(min_length=1, repr=False)
    postgres_db: str = Field(min_length=1)
    postgres_host: str = Field(min_length=1)
    postgres_port: int = Field(ge=1, le=65535)

    bank_a_base_url: HttpUrl = HttpUrl("http://localhost:3001")
    bank_b_base_url: HttpUrl = HttpUrl("http://localhost:3002")
    bank_timeout_seconds: float = Field(default=5.0, gt=0, allow_inf_nan=False)

    session_cookie_secure: bool = False
    allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        normalized = []
        for origin in origins:
            url = HttpUrl(origin)
            if (
                "*" in origin
                or urlsplit(origin).path not in ("", "/")
                or "\\" in origin
                or any(
                    char.isspace() or ord(char) < 32 or ord(char) == 127
                    for char in origin
                )
                or url.username is not None
                or url.password is not None
                or url.path not in (None, "/")
                or url.query is not None
                or url.fragment is not None
            ):
                raise ValueError("Allowed origins must be explicit HTTP(S) origins.")
            value = str(url).rstrip("/")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @field_validator("postgres_user", "postgres_db", "postgres_host")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("PostgreSQL settings must not be blank.")
        return value
