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

    # Phase 2: Local AI services
    ollama_url: str = "http://localhost:11434"
    comfyui_url: str = "http://localhost:8188"

    # Phase 2: Cloud AI APIs (empty = disabled / optional)
    fal_key: str = ""  # fal.ai API key — empty means Ken Burns fallback

    # Phase 2: YouTube upload
    youtube_client_secrets: str = ""  # path to OAuth2 client secrets JSON

    # Phase 2: Cost tracking
    cost_log_path: str = "data/cost_log.json"

    # Phase 2: Config directories
    channel_configs_dir: str = "src/channel_configs"
    prompt_templates_dir: str = "src/prompt_templates"

    # Phase 2: Assets
    font_path: str = "assets/fonts/NotoSansKR-Bold.ttf"


settings = Settings()
