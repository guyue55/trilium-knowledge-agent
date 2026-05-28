# -*- coding: utf-8 -*-
"""应用程序配置管理."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from loguru import logger

# 加载.env文件
_ = load_dotenv()


class ConfigError(Exception):
    """配置相关的异常."""

    pass


# 常量定义
class ConfigConstants:
    """配置常量类，用于存储硬编码的配置值.

    将所有魔法数字和字符串集中管理，便于维护和调整。
    """

    # ============================================
    # 文本分割参数
    # ============================================
    DEFAULT_CHUNK_SIZE: int = 800
    """默认文本块大小（字符数）"""

    DEFAULT_CHUNK_OVERLAP: int = 150
    """默认文本块重叠大小（字符数）"""

    # ============================================
    # 搜索参数
    # ============================================
    DEFAULT_SEARCH_K: int = 10
    """默认检索文档数量"""

    MAX_SEARCH_RESULTS: int = 20
    """最大搜索结果数量"""

    MMR_FETCH_K_MULTIPLIER: int = 2
    """MMR搜索时fetch_k是search_k的倍数"""

    MMR_LAMBDA_MULT: float = 0.3
    """MMR多样性参数，偏向相关性"""

    # ============================================
    # 批处理参数
    # ============================================
    VECTOR_DB_BATCH_SIZE: int = 5000
    """向量数据库批量操作大小"""

    VECTOR_DB_PERSIST_INTERVAL: int = 3
    """向量数据库持久化间隔（每N批）"""

    # ============================================
    # 重试参数
    # ============================================
    DEFAULT_MAX_RETRIES: int = 5
    """默认最大重试次数"""

    DEFAULT_RETRY_BACKOFF_FACTOR: float = 1.0
    """重试退避因子（秒）"""

    # ============================================
    # 超时参数（秒）
    # ============================================
    TRILIUM_API_TIMEOUT: int = 30
    """Trilium API请求超时时间"""

    VECTOR_DB_QUERY_TIMEOUT: int = 10
    """向量数据库查询超时时间"""

    LLM_GENERATION_TIMEOUT: int = 120
    """LLM生成超时时间"""

    # ============================================
    # 内容过滤参数
    # ============================================
    MIN_CONTENT_LENGTH: int = 10
    """笔记内容的最小长度（字符数）"""

    VALID_NOTE_TYPES: list[str] = ["text", "code", "doc", "book"]
    """有效的笔记类型列表"""

    BINARY_MIME_PREFIXES: list[str] = ["image/", "audio/", "video/"]
    """二进制MIME类型前缀列表"""

    # ============================================
    # API限制参数
    # ============================================
    MAX_QUESTION_LENGTH: int = 1000
    """问题的最大长度（字符数）"""

    # ============================================
    # 缓存配置
    # ============================================
    QA_CACHE_SIZE: int = 100
    """问答缓存容量"""

    QA_CACHE_TTL: int = 3600
    """问答缓存过期时间（秒）"""

    # ============================================
    # 安全配置
    # ============================================
    API_KEY_HEADER_NAME: str = "X-API-Key"
    """API Key 请求头名称"""


class Config:
    """应用程序配置类.

    负责从环境变量加载配置，并提供验证和默认值。
    所有配置项都有完整的类型注解，确保类型安全。
    """

    def __init__(self) -> None:
        """初始化配置并进行验证."""
        # ============================================
        # Trilium配置
        # ============================================
        self.trilium_base_url: str = os.getenv("TRILIUM_BASE_URL", "http://localhost:8080")
        self.trilium_token: str = os.getenv("TRILIUM_TOKEN", "")
        self.trilium_data_dir: str = os.getenv("TRILIUM_DATA_DIR", "./data/trilium")
        self.note_ids: list[str] = os.getenv("TRILIUM_NOTE_IDS", "root").split(",")

        # 验证并转换深度和限制参数
        try:
            self.depth: int = int(os.getenv("TRILIUM_EXPORT_DEPTH", "10"))
        except ValueError:
            logger.warning("TRILIUM_EXPORT_DEPTH 不是有效的整数，默认使用 10")
            self.depth = 10

        try:
            self.limit: int = int(os.getenv("TRILIUM_EXPORT_LIMIT", "5000"))
        except ValueError:
            logger.warning("TRILIUM_EXPORT_LIMIT 不是有效的整数，默认使用 5000")
            self.limit = 5000

        # ============================================
        # 向量数据库配置
        # ============================================
        self.vector_db_dir: str = os.getenv("VECTOR_DB_DIR", "./data/vector_db/embeddings")

        # ============================================
        # 嵌入模型配置
        # ============================================
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.embedding_model_local_path: str = os.getenv(
            "EMBEDDING_MODEL_LOCAL_PATH",
            "./data/models/sentence-transformers/all-MiniLM-L6-v2",
        )

        # ============================================
        # 语言模型配置
        # ============================================
        self.llm_model_path: str = os.getenv("LLM_MODEL_PATH", "./data/models/gpt4all/ggml-gpt4all-j-v1.3-groovy.bin")
        self.llm_model_type: str = os.getenv("LLM_MODEL_TYPE", "gpt4all")
        self.llm_use_api: bool = os.getenv("LLM_USE_API", "false").lower() == "true"

        self.qwen_api_key: str = os.getenv("QWEN_API_KEY", "")

        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_api_base: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.openai_model_name: str = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

        # ============================================
        # 检索配置
        # ============================================
        try:
            self.search_k: int = int(os.getenv("SEARCH_K", str(ConfigConstants.DEFAULT_SEARCH_K)))
        except ValueError:
            logger.warning(f"SEARCH_K 不是有效的整数，默认使用 {ConfigConstants.DEFAULT_SEARCH_K}")
            self.search_k = ConfigConstants.DEFAULT_SEARCH_K

        # ============================================
        # 文本分割配置
        # ============================================
        try:
            self.chunk_size: int = int(os.getenv("CHUNK_SIZE", str(ConfigConstants.DEFAULT_CHUNK_SIZE)))
        except ValueError:
            logger.warning(f"CHUNK_SIZE 不是有效的整数，使用默认值 {ConfigConstants.DEFAULT_CHUNK_SIZE}")
            self.chunk_size = ConfigConstants.DEFAULT_CHUNK_SIZE

        try:
            self.chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", str(ConfigConstants.DEFAULT_CHUNK_OVERLAP)))
        except ValueError:
            logger.warning(f"CHUNK_OVERLAP 不是有效的整数，使用默认值 {ConfigConstants.DEFAULT_CHUNK_OVERLAP}")
            self.chunk_overlap = ConfigConstants.DEFAULT_CHUNK_OVERLAP

        # ============================================
        # 镜像源配置
        # ============================================
        self.hf_endpoint: str = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

        # ============================================
        # 安全配置
        # ============================================
        self.api_auth_key: str = os.getenv("API_AUTH_KEY", "")
        """用于 API 访问认证的密钥"""

        # 执行配置验证
        self.validate()

    def validate(self) -> None:
        """验证配置的有效性.

        Raises:
            ConfigError: 当配置验证失败时抛出.
        """
        errors: list[str] = []

        # 验证必要的配置项
        if not self.trilium_token.strip():
            errors.append("TRILIUM_TOKEN 不能为空，否则无法连接到 Trilium")

        if not self.trilium_base_url.strip():
            errors.append("TRILIUM_BASE_URL 不能为空")

        # 检查数值配置的有效性
        if self.depth <= 0:
            errors.append(f"TRILIUM_EXPORT_DEPTH 必须大于 0，当前值: {self.depth}")

        if self.limit <= 0:
            errors.append(f"TRILIUM_EXPORT_LIMIT 必须大于 0，当前值: {self.limit}")

        if self.search_k <= 0:
            errors.append(f"SEARCH_K 必须大于 0，当前值: {self.search_k}")

        if self.search_k > ConfigConstants.MAX_SEARCH_RESULTS:
            logger.warning(f"SEARCH_K ({self.search_k}) 超过最大值 {ConfigConstants.MAX_SEARCH_RESULTS}，将使用最大值")
            self.search_k = ConfigConstants.MAX_SEARCH_RESULTS

        if self.chunk_size <= 0:
            errors.append(f"CHUNK_SIZE 必须大于 0，当前值: {self.chunk_size}")

        if self.chunk_overlap < 0:
            errors.append(f"CHUNK_OVERLAP 不能为负数，当前值: {self.chunk_overlap}")

        if self.chunk_overlap >= self.chunk_size:
            errors.append(f"CHUNK_OVERLAP ({self.chunk_overlap}) 必须小于 CHUNK_SIZE ({self.chunk_size})")

        # 检查模型类型
        valid_llm_types = ["gpt4all", "qwen", "openai"]
        if self.llm_model_type.lower() not in valid_llm_types:
            errors.append(f"LLM_MODEL_TYPE 必须是 {valid_llm_types} 之一，当前值: {self.llm_model_type}")

        # 如果是qwen类型且没有API密钥，给出提示（不是错误）
        if self.llm_model_type.lower() == "qwen" and self.llm_use_api and not self.qwen_api_key.strip():
            errors.append("已启用 LLM_USE_API，但未设置 QWEN_API_KEY")

        # 如果是openai类型且没有API密钥，给出提示
        if self.llm_model_type.lower() == "openai" and not self.openai_api_key.strip():
            errors.append("LLM_MODEL_TYPE 为 openai，但未设置 OPENAI_API_KEY")

        # 记录验证错误
        if errors:
            error_msg = "配置验证失败:\n" + "\n".join([f"  - {err}" for err in errors])
            logger.error(error_msg)
            raise ConfigError(error_msg)

        logger.info("配置验证成功")

    def __repr__(self) -> str:
        """返回配置的字符串表示（隐藏敏感信息）.

        Returns:
            str: 配置的字符串表示.
        """
        return (
            f"Config("
            f"trilium_base_url={self.trilium_base_url}, "
            f"llm_model_type={self.llm_model_type}, "
            f"search_k={self.search_k}, "
            f"chunk_size={self.chunk_size}"
            f")"
        )


def get_config() -> Config:
    """获取应用程序配置实例.

    Returns:
        Config: 应用程序配置实例.
    """
    return Config()
