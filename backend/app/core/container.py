# -*- coding: utf-8 -*-
"""应用生命周期容器管理.

用于存储全局单例（如模型、数据库连接），并提供清晰的类型注解。
"""

from typing import Optional
from loguru import logger

from app.core.config import Config, get_config
from app.llm.base import LLMAdapter
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager, MemoryManager
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter

class AppContainer:
    """全局单例组件容器."""
    
    def __init__(self):
        self.config: Config = get_config()
        self.llm_adapter: Optional[LLMAdapter] = None
        self.vector_store: Optional[VectorStoreAdapter] = None
        self.reranker: Optional[Reranker] = None
        self.cache_manager: Optional[CacheManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.memory_manager: Optional[MemoryManager] = None
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

        # ⚡ 2026 Concurrency Safe: 清理 Trilium 全局共享 Session 连接池，彻底杜绝套接字泄露
        try:
            from app.trilium.client import _shared_session
            if _shared_session:
                logger.info("🔌 AppContainer: 正在清理 Trilium 全局共享 Session 连接池...")
                _shared_session.close()
                logger.info("🔌 AppContainer: Trilium 共享 Session 已安全关闭。")
        except Exception as e:
            logger.error(f"清理 Trilium 共享 Session 时出错: {e}")

# 全局唯一容器实例
container = AppContainer()
