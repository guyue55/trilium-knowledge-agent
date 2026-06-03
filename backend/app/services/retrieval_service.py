# -*- coding: utf-8 -*-
"""检索与重排服务.

专门负责与 VectorStore (LanceDB) 和 Reranker 交互的高内聚服务模块。
"""

import asyncio
from typing import Any, List, Tuple
from loguru import logger

from app.core.config import Config
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter
from app.retrieval.document import Document

class RetrievalService:
    def __init__(
        self, 
        config: Config, 
        vector_store: VectorStoreAdapter, 
        reranker: Reranker = None
    ):
        self.config = config
        self.vector_store = vector_store
        self.reranker = reranker

    async def retrieve_and_rerank(self, query: str) -> Tuple[List[Document], List[Tuple[Document, float]]]:
        """
        执行两阶段检索（混合搜索召回 + 重排）并返回结果。
        
        Returns:
            Tuple: 
                - filtered_docs: 经过重排和过滤的文档列表。
                - raw_docs: 原始带相似度分数的文档列表（用于最终提取分数组装 Source）。
        """
        logger.debug(f"RetrievalService: 开始执行混合检索，查询词 = '{query}'")
        
        # 第一阶段：混合召回 (LanceDB 原生支持 Vector + FTS)
        raw_docs = await asyncio.to_thread(
            self.vector_store.similarity_search_with_scores,
            query, 
            k=self.config.search_k * 2,
            score_threshold=0.0
        )
        
        if not raw_docs:
            logger.debug("混合搜索未召回任何内容")
            return [], []
            
        logger.debug(f"第一阶段召回了 {len(raw_docs)} 个文档块")

        # 第二阶段：质量重排与过滤
        if self.reranker:
            filtered_docs = await asyncio.to_thread(
                self.reranker.rerank_and_filter,
                raw_docs, 
                query
            )
        else:
            # 如果没有重排器，就按照设定的 Top K 截断
            filtered_docs = [doc for doc, score in raw_docs[:self.config.search_k]]
            
        logger.debug(f"RetrievalService: 检索完成，最终返回 {len(filtered_docs)} 条高质量切片")
        return filtered_docs, raw_docs
