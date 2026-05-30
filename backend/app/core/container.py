# -*- coding: utf-8 -*-
"""应用生命周期容器管理.

用于存储全局单例（如模型、数据库连接），并提供清晰的类型注解。
"""

from typing import Optional
from loguru import logger

from app.core.config import Config, get_config
from app.llm.base import LLMAdapter
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager
from app.retrieval.bm25 import BM25StoreAdapter
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter

class AppContainer:
    """全局单例组件容器."""
    
    def __init__(self):
        self.config: Config = get_config()
        self.llm_adapter: Optional[LLMAdapter] = None
        self.vector_store: Optional[VectorStoreAdapter] = None
        self.bm25_store: Optional[BM25StoreAdapter] = None
        self.reranker: Optional[Reranker] = None
        self.cache_manager: Optional[CacheManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.init_errors: list[str] = []

    def set_error(self, error_msg: str):
        self.init_errors.append(error_msg)
        logger.error(f"Container Error: {error_msg}")

    def cleanup(self):
        """释放所有组件资源."""
        if self.llm_adapter and hasattr(self.llm_adapter, "cleanup"):
            try:
                self.llm_adapter.cleanup()
            except Exception as e:
                logger.error(f"清理 LLM Adapter 时出错: {e}")

# 全局唯一容器实例
container = AppContainer()
