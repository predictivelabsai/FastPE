from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = Field(default="", alias="DB_URL")
    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    xai_base_url: str = Field(default="https://api.x.ai/v1", alias="XAI_BASE_URL")
    xai_model: str = Field(default="grok-4-fast-reasoning", alias="XAI_MODEL")
    xai_agent_model: str = Field(default="grok-4", alias="XAI_AGENT_MODEL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")

    # Web search (Tavily default, EXA fallback)
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")

    # Baltic registries + tax authorities (optional; see docs/registry_integration.md)
    lt_cr_api_key: str = Field(default="", alias="LT_CR_API_KEY")
    lt_vmi_api_key: str = Field(default="", alias="LT_VMI_API_KEY")
    lv_ur_api_key: str = Field(default="", alias="LV_UR_API_KEY")
    lv_vid_api_key: str = Field(default="", alias="LV_VID_API_KEY")
    # Estonia Äriregister uses SOAP with username + password (issued by RIK).
    # EE_ARI_API_KEY is kept for back-compat / stub detection; prefer the
    # EE_ARI_USERNAME + EE_ARI_PASSWORD pair for the real SOAP endpoint.
    ee_ari_api_key: str = Field(default="", alias="EE_ARI_API_KEY")
    ee_ari_username: str = Field(default="", alias="EE_ARI_USERNAME")
    ee_ari_password: str = Field(default="", alias="EE_ARI_PASSWORD")
    ee_emta_api_key: str = Field(default="", alias="EE_EMTA_API_KEY")

    # Pipedrive CRM
    pipedrive_api_token: str = Field(default="", alias="PIPEDRIVE_API_TOKEN")
    pipedrive_domain: str = Field(default="", alias="PIPEDRIVE_DOMAIN")

    # Postmark email
    postmark_api_token: str = Field(default="", alias="POSTMARK_API_TOKEN")
    postmark_from_email: str = Field(default="info@pehero.chat", alias="POSTMARK_FROM_EMAIL")
    daily_deals_to_email: str = Field(default="", alias="DAILY_DEALS_TO_EMAIL")

    # News feed
    news_interval_seconds: int = Field(default=1800, alias="NEWS_INTERVAL_SECONDS")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_secret: str = Field(default="change-me", alias="APP_SECRET")
    port: int = Field(default=5058, alias="PORT")


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
