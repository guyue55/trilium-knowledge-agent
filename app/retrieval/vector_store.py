# -*- coding: utf-8 -*-
"""向量库存储与搜索适配器."""

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import Config, ConfigConstants


class VectorStoreAdapter(ABC):
    """向量数据库接口基类."""

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def add_documents(self, documents: List[Any]) -> None:
        pass

    @abstractmethod
    def similarity_search_with_scores(self, query: str, k: int = 5, score_threshold: float = 0.0) -> List[tuple[Any, float]]:
        pass

    @abstractmethod
    def get_retriever(self, search_kwargs: Dict[str, Any]) -> Any:
        pass


class ChromaAdapter(VectorStoreAdapter):
    """ChromaDB 适配器实现."""

    def __init__(self, config: Config, embedding_model: Any):
        self.config = config
        self.embedding_model = embedding_model
        self.vector_store = None
        self._db_lock = threading.Lock()

    def initialize(self) -> bool:
        if not self.embedding_model:
            logger.error("Embedding 模型为空，Chroma 无法初始化")
            return False
            
        try:
            from langchain_community.vectorstores import Chroma

            self.vector_store = Chroma(
                embedding_function=self.embedding_model,
                persist_directory=self.config.vector_db_dir,
            )
            logger.info("ChromaDB 初始化成功")
            return True
        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {e}")
            return False

    def clear(self) -> None:
        if not self.vector_store:
            return
        try:
            logger.info("正在清空向量数据库...")
            with self._db_lock:
                self.vector_store.delete_collection()
                from langchain_community.vectorstores import Chroma

                self.vector_store = Chroma(
                    embedding_function=self.embedding_model,
                    persist_directory=self.config.vector_db_dir,
                )
                if hasattr(self.vector_store, "persist"):
                    self.vector_store.persist()
            logger.info("向量数据库清空完毕")
        except Exception as e:
            logger.error(f"清空向量库时出错: {e}")

    def add_documents(self, documents: List[Any]) -> None:
        if not self.vector_store or not documents:
            return

        total_docs = len(documents)
        batch_size = ConfigConstants.VECTOR_DB_BATCH_SIZE

        try:
            for i in range(0, total_docs, batch_size):
                batch = documents[i : i + batch_size]
                current_batch = i // batch_size + 1
                total_batches = (total_docs + batch_size - 1) // batch_size
                
                logger.info(f"添加文档批次 {current_batch}/{total_batches} (进度: {min(i + batch_size, total_docs)}/{total_docs})...")
                with self._db_lock:
                    self.vector_store.add_documents(batch)
                    
                    if hasattr(self.vector_store, "persist"):
                        if current_batch == total_batches or current_batch % 3 == 0:
                            self.vector_store.persist()
        except Exception as e:
            logger.error(f"添加文档到 ChromaDB 失败: {e}")

    def similarity_search_with_scores(self, query: str, k: int = 5, score_threshold: float = 0.0) -> List[tuple[Any, float]]:
        if not self.vector_store:
            return []
        try:
            with self._db_lock:
                return self.vector_store.similarity_search_with_relevance_scores(
                    query, k=k, score_threshold=score_threshold
                )
        except Exception as e:
            logger.error(f"ChromaDB 搜索失败: {e}")
            return []

    def get_retriever(self, search_kwargs: Dict[str, Any]) -> Any:
        if not self.vector_store:
            return None
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)
