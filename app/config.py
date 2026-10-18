from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


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
