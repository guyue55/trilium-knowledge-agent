# -*- coding: utf-8 -*-
"""文本向量化（Embedding）适配器."""

from typing import Any, List
from loguru import logger
from app.core.config import Config


class MockTextEmbedding:
    """极简本地伪向量嵌入模型，当没有 FastEmbed 时提供 0.0 向量降级测试."""
    
    def __init__(self, size: int = 384):
        self.size = size

    def embed(self, texts: List[str]) -> Any:
        """迭代生成伪向量结果."""
        class DummyVector:
            def __init__(self, size: int):
                self._vec = [0.0] * size
                
            def tolist(self) -> List[float]:
                return self._vec
                
        for _ in texts:
            yield DummyVector(self.size)


class EmbeddingAdapter:
    """文本向量化模型封装 (FastEmbed 驱动 & Mock 自适应降级)."""

    def __init__(self, config: Config):
        self.config = config
        self.embedding_model = None
        self.is_mocked = False

    def initialize(self) -> bool:
        """初始化加载 FastEmbed 向量模型，失败则自动优雅降级为伪向量."""
        try:
            # 尝试导入并使用 FastEmbed
            from fastembed import TextEmbedding
            
            # 使用配置中的模型名，默认可以回退到一个很小的中文推荐模型
            model_name = self.config.embedding_model if self.config.embedding_model != "./data/models/sentence-transformers/all-MiniLM-L6-v2" else "BAAI/bge-small-zh-v1.5"

            logger.info(f"正在加载 FastEmbed 模型: {model_name}")
            
            # FastEmbed 会自动在本地 ./data/models/fastembed 下载并缓存
            self.embedding_model = TextEmbedding(model_name=model_name, cache_dir="./data/models/fastembed")
            self.is_mocked = False
            logger.info("Embedding 适配器 (FastEmbed) 初始化成功")
            return True
        except Exception as e:
            logger.warning(f"Embedding 初始化异常: {e}，将无缝降级为 Native MockEmbedding 进行降级模拟测试")
            # 优雅地创建内置 Mock 向量，完全不报错，避免阻断后端生命周期的拉起
            self.embedding_model = MockTextEmbedding(size=384)
            self.is_mocked = True
            return False

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self.embedding_model:
            return []
        try:
            # FastEmbed 返回 generator，将其转换为 list[float]
            embeddings = list(self.embedding_model.embed(texts))
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"批量 Embedding 失败: {e}")
            return []
            
    def embed_query(self, text: str) -> List[float]:
        if not self.embedding_model:
            return []
        try:
            embeddings = list(self.embedding_model.embed([text]))
            if embeddings:
                return embeddings[0].tolist()
            return []
        except Exception as e:
            logger.error(f"Query Embedding 失败: {e}")
            return []

    def get_model(self) -> Any:
        return self.embedding_model
