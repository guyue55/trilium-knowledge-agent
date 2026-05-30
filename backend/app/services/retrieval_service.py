# -*- coding: utf-8 -*-
"""检索与重排服务.

专门负责与 VectorStore 和 Reranker 交互的高内聚服务模块。
"""

import asyncio
from typing import Any, Dict, List, Tuple
from loguru import logger

from app.core.config import Config
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter

class RetrievalService:
    def __init__(
        self, 
        config: Config, 
        vector_store: VectorStoreAdapter, 
        reranker: Reranker
    ):
        self.config = config
        self.vector_store = vector_store
        self.reranker = reranker

    async def retrieve_and_rerank(self, query: str) -> Tuple[List[Any], List[Tuple[Any, float]]]:
        """
        执行两阶段检索（召回 + 重排）并返回结果。
        
        Returns:
            Tuple: 
                - filtered_docs: 经过重排和过滤的文档列表。
                - raw_docs: 原始带相似度分数的文档列表（用于最终提取分数组装 Source）。
        """
        logger.debug(f"RetrievalService: 开始执行两阶段检索，查询词 = '{query}'")
        
        # 第一阶段：向量检索 (放入线程池以防阻塞主事件循环)
        raw_docs = await asyncio.to_thread(
            self.vector_store.similarity_search_with_scores,
            query, 
            k=self.config.search_k * 2
        )
        
        if not raw_docs:
            logger.debug("向量检索未召回任何内容")
            return [], []

        # 第二阶段：质量重排与过滤 (放入线程池以防阻塞)
        filtered_docs = await asyncio.to_thread(
            self.reranker.rerank_and_filter,
            raw_docs, 
            query
        )
        
        logger.debug(f"RetrievalService: 检索完成，最终召回 {len(filtered_docs)} 条高质量切片")
        return filtered_docs, raw_docs
