# -*- coding: utf-8 -*-
"""检索与重排服务.

专门负责与 VectorStore (LanceDB) 和 Reranker 交互的高内聚服务模块。
"""

import asyncio
import time
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
        
        # ⚡ 效率与并发重塑：Reranker 检索热缓存屏障 (Cache Barrier)
        self._rerank_cache = {}  # 格式: {query_key: (timestamp, filtered_docs, raw_docs)}
        self._rerank_cache_max_size = 20
        self._rerank_cache_ttl = 300.0  # 缓存 5 分钟

    async def retrieve_and_rerank(self, query: str) -> Tuple[List[Document], List[Tuple[Document, float]]]:
        """
        执行两阶段检索（混合搜索召回 + 重排）并返回结果 (带 5 分钟高一致性热缓存防线，且支持树形层级聚合合并)。
        
        Returns:
         Tuple: 
             - filtered_docs: 经过重排、过滤及树状分片合并折叠的高质量文档列表。
             - raw_docs: 原始带相似度分数的文档列表。
         """
        # 根据 response_mode 自适应调整检索 K 值与重排阈值，并在缓存键中隔离不同模式的查询结果
        raw_mode = getattr(self.config, "response_mode", "balanced")
        response_mode = raw_mode.lower() if isinstance(raw_mode, str) else "balanced"
        query_key = f"{response_mode}:{query.strip().lower()}"
        current_time = time.time()
        
        # 1. 检查检索重排热缓存
        if query_key in self._rerank_cache:
            cache_time, cached_filtered, cached_raw = self._rerank_cache[query_key]
            if current_time - cache_time < self._rerank_cache_ttl:
                logger.info(f"🚀 RetrievalService: 检索重排热缓存命中！绕过 VectorStore 检索与 Reranker 本地推理。")
                return cached_filtered, cached_raw
            else:
                del self._rerank_cache[query_key]

        logger.debug(f"RetrievalService: 开始执行混合检索，模式 = '{response_mode}', 查询词 = '{query}'")

        if response_mode == "strict":
            search_k = 3
            reranker_threshold = 0.55
        elif response_mode == "creative":
            search_k = 6
            reranker_threshold = 0.25
        else: # balanced
            # 兼容单元测试中的 Mock 对象，防止 mock_config 的属性类型不匹配报错
            try:
                search_k = int(self.config.search_k) if int(self.config.search_k) > 0 else 4
            except (ValueError, TypeError):
                search_k = 4
                
            try:
                reranker_threshold = float(self.config.reranker_threshold) if float(self.config.reranker_threshold) > 0.0 else 0.40
            except (ValueError, TypeError):
                reranker_threshold = 0.40
        
        # 第一阶段：混合召回 (LanceDB 原生支持 Vector + FTS)
        import inspect
        search_res = self.vector_store.similarity_search_with_scores(
            query, 
            k=search_k * 2,
            score_threshold=0.0
        )
        if inspect.iscoroutine(search_res) or asyncio.iscoroutine(search_res):
            raw_docs = await search_res
        else:
            raw_docs = search_res
        
        if not raw_docs:
            logger.debug("混合搜索未召回任何内容")
            # 同样对空检索进行一个简短缓存，防止空检索频繁打盘
            self._rerank_cache[query_key] = (current_time, [], [])
            return [], []
            
        # 将原始相似度分数写入文档 metadata，便于树状合并直接引用与简化 Sources 接口数据链
        for doc, score in raw_docs:
            doc.metadata["score"] = score
            
        logger.debug(f"第一阶段召回了 {len(raw_docs)} 个文档块")

        # 第二阶段：质量重排与过滤
        if self.reranker:
            filtered_docs = await asyncio.to_thread(
                self.reranker.rerank_and_filter,
                raw_docs, 
                query,
                search_k=search_k,
                threshold=reranker_threshold
            )
        else:
            # 如果没有重排器，就按照设定的 Top K 截断
            filtered_docs = [doc for doc, score in raw_docs[:search_k]]
            
        # ⚡ 2026 前沿 RAG 重塑：对重排后的知识分片执行 Tree-Grouping 树形折叠去重
        filtered_docs = self._rollup_and_deduplicate_chunks(filtered_docs)
            
        logger.debug(f"RetrievalService: 检索与折叠完成，最终返回 {len(filtered_docs)} 条高质量合并切片")
        
        # 2. 塞入热缓存，并进行 FIFO 容量控制
        if len(self._rerank_cache) >= self._rerank_cache_max_size:
            oldest_key = min(self._rerank_cache.keys(), key=lambda k: self._rerank_cache[k][0])
            del self._rerank_cache[oldest_key]
            
        self._rerank_cache[query_key] = (current_time, filtered_docs, raw_docs)
        
        return filtered_docs, raw_docs

    def _rollup_and_deduplicate_chunks(self, docs: List[Document]) -> List[Document]:
        """将属于相同 note_id 的知识分片进行高内聚合并，消除重叠文本并重新分配元数据 (Milestone 16)."""
        if not docs:
            return []
            
        from collections import defaultdict
        grouped_docs = defaultdict(list)
        for doc in docs:
            note_id = doc.metadata.get("note_id")
            if note_id:
                grouped_docs[note_id].append(doc)
            else:
                # 若无 note_id，归档到独立分组不参与物理合并，完全防崩溃
                grouped_docs[id(doc)].append(doc)
                
        rolled_up_docs = []
        for note_id, group in grouped_docs.items():
            if len(group) == 1:
                rolled_up_docs.append(group[0])
            else:
                # 按 chunk_index 进行物理时序正向排序 (添加鲁棒的整型转换防错)
                def _get_chunk_index(d):
                    val = d.metadata.get("chunk_index", 0)
                    try:
                        return int(val) if val is not None else 0
                    except (ValueError, TypeError):
                        return 0
                group.sort(key=_get_chunk_index)
                
                merged_contents = []
                for doc in group:
                    content = doc.page_content.strip()
                    if not merged_contents:
                        merged_contents.append(content)
                    else:
                        last_content = merged_contents[-1]
                        # 简单的重合防溢出处理
                        if content in last_content:
                            continue
                        merged_contents.append(content)
                        
                merged_text = "\n\n... [ 跨段落知识拼接 ] ...\n\n".join(merged_contents)
                
                # 级联最高得分
                max_score = max(doc.metadata.get("score", 0.0) for doc in group)
                
                merged_meta = group[0].metadata.copy()
                merged_meta["chunk_index"] = "merged"
                merged_meta["is_merged"] = True
                merged_meta["score"] = max_score
                
                rolled_up_docs.append(Document(
                    page_content=merged_text,
                    metadata=merged_meta
                ))
        return rolled_up_docs


