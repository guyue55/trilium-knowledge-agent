# -*- coding: utf-8 -*-
"""应用程序配置管理."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from loguru import logger
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 计算物理绝对项目根目录，无论在哪个工作目录下启动进程，路径一律以此为基准进行标准化
# 兼容容器挂载卷模式：在容器内，宿主机上的 ./backend 被挂载为 /app，./data 被挂载为 /app/data。
_current_file = Path(__file__).resolve()
# _current_file = .../app/core/config.py 或 .../backend/app/core/config.py
_lvl3 = _current_file.parent.parent.parent # 对应 backend 或容器内的 /app
if _lvl3.name == "app" or str(_lvl3) == "/app" or _lvl3 == Path("/"):
    PROJECT_ROOT = Path("/app")
else:
    PROJECT_ROOT = _lvl3.parent




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
    reranker_model: str = Field(default="Xenova/ms-marco-MiniLM-L-6-v2")
    reranker_model_local_path: str = Field(default="./data/models/Xenova/ms-marco-MiniLM-L-6-v2")
    reranker_top_k: int = Field(default=5, ge=1)
    reranker_threshold: float = Field(default=0.0)

    # ============================================
    # 语言模型配置
    # ============================================
    llm_model_path: str = Field(default="qwen2.5:7b")
    llm_model_type: str = Field(default="ollama")
    llm_use_api: bool = Field(default=False)
    qwen_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    openai_api_base: str = Field(default="https://api.openai.com/v1")
    openai_model_name: str = Field(default="gpt-3.5-turbo")
    
    # 现代大模型 (DeepSeek & Gemini) 支持
    deepseek_api_key: str = Field(default="", repr=False)
    deepseek_api_base: str = Field(default="https://api.deepseek.com/v1")
    deepseek_model_name: str = Field(default="deepseek-chat")
    
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model_name: str = Field(default="gemini-2.5-flash")

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
    response_mode: str = Field(default="balanced")

    # ============================================
    # 镜像源与安全配置
    # ============================================
    hf_endpoint: str = Field(default="https://hf-mirror.com")
    api_auth_key: str = Field(default="", repr=False)

    @model_validator(mode='after')
    def validate_complex_rules(self) -> "Config":
        """执行更复杂的关联校验规则，通过软警告和容错设计，提升开箱即用的部署体验。"""
        # 0. 相对路径归一化为绝对路径，确保在多运行目录或测试环境下，均指向唯一且正确的物理目录
        def normalize_to_absolute(path_str: str) -> str:
            p = Path(path_str)
            if not p.is_absolute():
                return str((PROJECT_ROOT / p).resolve())
            return str(p.resolve())

        self.trilium_data_dir = normalize_to_absolute(self.trilium_data_dir)
        self.vector_db_dir = normalize_to_absolute(self.vector_db_dir)
        self.embedding_model_local_path = normalize_to_absolute(self.embedding_model_local_path)
        self.reranker_model_local_path = normalize_to_absolute(self.reranker_model_local_path)


        warnings = []
        errors = []

        # 1. 标题与路径的基础验证（属于警告类，不阻断主进程，但限制某些功能的运行）
        if not self.trilium_token.strip() or self.trilium_token == "your_trilium_api_token_here":
            warnings.append("TRILIUM_TOKEN 尚未配置或使用的是示例占位符。知识库的[同步作业]将无法使用，但在本地您可以照常进行界面预览、调试 Mock/已有的问答会话。")

        if not self.trilium_base_url.strip():
            errors.append("TRILIUM_BASE_URL 不能为空")

        # 2. 核心分割约束（如果重叠大于等于块大小，属于致命算法逻辑错误，应该阻断）
        if self.chunk_overlap >= self.chunk_size:
            errors.append(f"CHUNK_OVERLAP ({self.chunk_overlap}) 必须小于 CHUNK_SIZE ({self.chunk_size})")

        # 3. LLM 模型的现代支持与柔性校验
        valid_llm_types = ["qwen", "openai", "ollama", "deepseek", "gemini"]
        model_type_lower = self.llm_model_type.lower()
        if model_type_lower not in valid_llm_types:
            errors.append(f"LLM_MODEL_TYPE 必须是 {valid_llm_types} 之一，当前值为 {self.llm_model_type}")

        if model_type_lower == "qwen" and self.llm_use_api and not self.qwen_api_key.strip():
            warnings.append("已启用通义千问 LLM_USE_API，但未在环境变量中提供 QWEN_API_KEY，大模型问答将自动切换为本地 Mock 降级体验")

        if model_type_lower == "openai" and not self.openai_api_key.strip():
            warnings.append("LLM_MODEL_TYPE 设为了 openai，但未提供 OPENAI_API_KEY，大模型问答将自动切换为本地 Mock 降级体验")
            
        if model_type_lower == "ollama" and not self.llm_model_path.strip():
            warnings.append("LLM_MODEL_TYPE 设为了 ollama，但未指定任何本地模型路径（如 qwen2:7b）。大模型问答将自动切换为本地 Mock 降级体验")

        if model_type_lower == "deepseek" and not self.deepseek_api_key.strip():
            warnings.append("LLM_MODEL_TYPE 设为了 deepseek，但未提供 DEEPSEEK_API_KEY，大模型问答将自动切换为本地 Mock 降级体验")

        if model_type_lower == "gemini" and not self.gemini_api_key.strip():
            warnings.append("LLM_MODEL_TYPE 设为了 gemini，但未提供 GEMINI_API_KEY，大模型问答将自动切换为本地 Mock 降级体验")

        # 4. 统一处理警告与错误
        if warnings:
            for warn in warnings:
                logger.warning(f"⚠️ [配置宽容提示] {warn}")

        if errors:
            error_msg = "❌ [配置验证失败] 致命配置错误:\n" + "\n".join([f"  - {err}" for err in errors])
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
