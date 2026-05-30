# -*- coding: utf-8 -*-
"""应用程序配置管理."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from loguru import logger
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """配置相关的异常."""
    pass


class ConfigConstants:
    """配置常量类，用于存储硬编码的配置值.
    将所有魔法数字和字符串集中管理，便于维护和调整。
    """
    # 搜索参数
    MAX_SEARCH_RESULTS: int = 20
    MMR_FETCH_K_MULTIPLIER: int = 2
    MMR_LAMBDA_MULT: float = 0.3

    # 内容过滤参数
    MIN_CONTENT_LENGTH: int = 10
    VALID_NOTE_TYPES: list[str] = ["text", "code", "doc", "book"]
    BINARY_MIME_PREFIXES: list[str] = ["image/", "audio/", "video/"]

    # API限制参数
    MAX_QUESTION_LENGTH: int = 1000

    # 安全配置
    API_KEY_HEADER_NAME: str = "X-API-Key"


class Config(BaseSettings):
    """应用程序配置类 (使用 Pydantic Settings 实现).
    
    自动从环境变量或 .env 文件读取配置，并提供强类型的验证和默认值。
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ============================================
    # Trilium配置
    # ============================================
    trilium_base_url: str = Field(default="http://localhost:8080")
    trilium_token: str = Field(default="", repr=False)
    trilium_data_dir: str = Field(default="./data/trilium")
    trilium_note_ids: str = Field(default="root")
    
    trilium_export_depth: int = Field(default=10, ge=1)
    trilium_export_limit: int = Field(default=5000, ge=1)

    @property
    def note_ids(self) -> List[str]:
        return [x.strip() for x in self.trilium_note_ids.split(",") if x.strip()]

    @property
    def depth(self) -> int:
        return self.trilium_export_depth

    @property
    def limit(self) -> int:
        return self.trilium_export_limit

    # ============================================
    # 向量数据库配置
    # ============================================
    vector_db_dir: str = Field(default="./data/vector_db/embeddings")

    # ============================================
    # 嵌入模型配置
    # ============================================
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_model_local_path: str = Field(default="./data/models/sentence-transformers/all-MiniLM-L6-v2")

    # ============================================
    # 重排序模型配置 (Reranker)
    # ============================================
    use_reranker: bool = Field(default=True)
    reranker_model: str = Field(default="BAAI/bge-reranker-base")
    reranker_model_local_path: str = Field(default="./data/models/BAAI/bge-reranker-base")
    reranker_top_k: int = Field(default=5, ge=1)

    # ============================================
    # 语言模型配置
    # ============================================
    llm_model_path: str = Field(default="./data/models/gpt4all/ggml-gpt4all-j-v1.3-groovy.bin")
    llm_model_type: str = Field(default="gpt4all")
    llm_use_api: bool = Field(default=False)
    qwen_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    openai_api_base: str = Field(default="https://api.openai.com/v1")
    openai_model_name: str = Field(default="gpt-3.5-turbo")

    # ============================================
    # 检索和分割配置
    # ============================================
    search_k: int = Field(default=10, ge=1, le=ConfigConstants.MAX_SEARCH_RESULTS)
    chunk_size: int = Field(default=800, ge=1)
    chunk_overlap: int = Field(default=150, ge=0)

    # ============================================
    # 批处理与网络配置
    # ============================================
    vector_db_batch_size: int = Field(default=5000, ge=100)
    vector_db_persist_interval: int = Field(default=3, ge=1)
    
    max_retries: int = Field(default=5, ge=0)
    retry_backoff_factor: float = Field(default=1.0, ge=0.0)
    
    trilium_api_timeout: int = Field(default=30, ge=1)
    vector_db_query_timeout: int = Field(default=10, ge=1)
    llm_generation_timeout: int = Field(default=120, ge=1)

    # ============================================
    # 缓存配置
    # ============================================
    qa_cache_size: int = Field(default=100, ge=0)
    qa_cache_ttl: int = Field(default=3600, ge=0)

    # ============================================
    # 镜像源与安全配置
    # ============================================
    hf_endpoint: str = Field(default="https://hf-mirror.com")
    api_auth_key: str = Field(default="", repr=False)

    @model_validator(mode='after')
    def validate_complex_rules(self) -> "Config":
        """执行更复杂的关联校验规则"""
        errors = []

        if not self.trilium_token.strip():
            errors.append("TRILIUM_TOKEN 不能为空，否则无法连接到 Trilium")

        if not self.trilium_base_url.strip():
            errors.append("TRILIUM_BASE_URL 不能为空")

        if self.chunk_overlap >= self.chunk_size:
            errors.append(f"CHUNK_OVERLAP ({self.chunk_overlap}) 必须小于 CHUNK_SIZE ({self.chunk_size})")

        valid_llm_types = ["gpt4all", "qwen", "openai"]
        if self.llm_model_type.lower() not in valid_llm_types:
            errors.append(f"LLM_MODEL_TYPE 必须是 {valid_llm_types} 之一")

        if self.llm_model_type.lower() == "qwen" and self.llm_use_api and not self.qwen_api_key.strip():
            errors.append("已启用 LLM_USE_API，但未设置 QWEN_API_KEY")

        if self.llm_model_type.lower() == "openai" and not self.openai_api_key.strip():
            errors.append("LLM_MODEL_TYPE 为 openai，但未设置 OPENAI_API_KEY")

        if errors:
            error_msg = "配置验证失败:\n" + "\n".join([f"  - {err}" for err in errors])
            logger.error(error_msg)
            raise ConfigError(error_msg)

        return self


@lru_cache()
def get_config() -> Config:
    """获取应用程序配置单例.

    Returns:
        Config: 应用程序配置实例.
    """
    return Config()
