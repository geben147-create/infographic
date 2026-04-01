from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Temporal (per D-03)
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"

    # Database (per D-05)
    database_url: str = "sqlite:///data/pipeline.db"

    # Google Sheets (per D-11 — empty defaults so app starts without Sheets config)
    google_sheets_credentials: str = ""  # path to service account JSON
    google_sheets_id: str = ""  # spreadsheet ID


settings = Settings()
