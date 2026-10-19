from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Form Filler AI"
    API_V1_STR: str = "/api/v1"

    # Database (provided from .env)
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="form_filler")

    # LLM Provider — backend choice: "ollama" | "openrouter"
    LLM_PROVIDER: str = Field(default="ollama")

    # Ollama
    OLLAMA_HOST: str = Field(default="http://host.docker.internal:11434")
    LLM_MODEL: str = Field(default="llama3.2:3b")
    LLM_NUM_CTX: int = Field(default=8192)
    LLM_TIMEOUT: float = Field(default=120.0)  # seconds

    # OpenRouter (left for compatibility, used if LLM_PROVIDER=openrouter)
    OPENROUTER_API_KEY: str = Field(default="")

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()