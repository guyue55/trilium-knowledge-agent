# -*- coding: utf-8 -*-
"""检索与重排服务.

专门负责与 VectorStore 和 Reranker 交互的高内聚服务模块。
"""

import asyncio
from typing import Any, Dict, List, Tuple
from loguru import logger

from app.core.config import Config
from app.retrieval.bm25 import BM25StoreAdapter
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter

class RetrievalService:
    def __init__(
        self, 
        config: Config, 
        vector_store: VectorStoreAdapter, 
        bm25_store: BM25StoreAdapter = None,
        reranker: Reranker = None
    ):
        self.config = config
        self.vector_store = vector_store
        self.bm25_store = bm25_store
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
        
        # 第一阶段：多路召回 (并发执行 Vector 和 BM25)
        vector_task = asyncio.to_thread(
            self.vector_store.similarity_search_with_scores,
            query, 
            k=self.config.search_k * 2
        )
        
        bm25_task = asyncio.sleep(0) # fallback
        if self.bm25_store:
            bm25_task = asyncio.to_thread(
                self.bm25_store.retrieve,
                query,
                k=self.config.search_k * 2
            )
            
        vector_raw, bm25_raw = await asyncio.gather(vector_task, bm25_task)
        vector_raw = vector_raw or []
        bm25_raw = bm25_raw or []
        
        # 去重合并 (保留基于 page_content 或 source_id 的唯一性)
        seen_contents = set()
        merged_docs_with_scores = []
        
        for doc, score in vector_raw:
            if doc.page_content not in seen_contents:
                seen_contents.add(doc.page_content)
                merged_docs_with_scores.append((doc, score))
                
        for doc in bm25_raw:
            if doc and getattr(doc, "page_content", None) and doc.page_content not in seen_contents:
                seen_contents.add(doc.page_content)
                # BM25 没有可比的相似度得分，给个占位符，统一交由 Reranker 裁决
                merged_docs_with_scores.append((doc, 0.0))
        
        if not merged_docs_with_scores:
            logger.debug("混合多路检索未召回任何内容")
            return [], []

        # 第二阶段：质量重排与过滤 (放入线程池以防阻塞)
        filtered_docs = await asyncio.to_thread(
            self.reranker.rerank_and_filter,
            merged_docs_with_scores, 
            query
        )
        
        logger.debug(f"RetrievalService: 检索完成，最终召回 {len(filtered_docs)} 条高质量切片")
        return filtered_docs, merged_docs_with_scores
