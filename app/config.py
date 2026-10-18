from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    model_mode: Literal['api', 'demo'] = 'api'
    llm_base_url: str = ''
    llm_api_key: str = ''
    llm_model: str = ''
    embedding_base_url: str = ''
    embedding_api_key: str = ''
    embedding_model: str = ''
    embedding_dim: int = 1024
    qdrant_url: str = ''
    data_dir: str = 'data'
    rerank_base_url: str = ''
    rerank_api_key: str = ''
    rerank_model: str = ''
    model_timeout_seconds: float = Field(default=60, ge=1, le=300)
    model_connect_timeout_seconds: float = Field(default=10, ge=1, le=60)
    model_max_retries: int = Field(default=2, ge=0, le=4)
    model_retry_max_delay_seconds: float = Field(default=5, ge=0, le=30)
    model_stream_max_seconds: float = Field(default=180, ge=1, le=600)
