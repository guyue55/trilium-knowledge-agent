# -*- coding: utf-8 -*-
"""检索结果重排与质量过滤."""

from typing import Any, List

from loguru import logger

from app.core.config import Config


class Reranker:
    """实现对召回文档的质量筛选（宁缺毋滥）和排序."""

    def __init__(self, config: Config):
        self.config = config

    def rerank_and_filter(self, docs_with_scores: List[tuple[Any, float]], question: str) -> List[Any]:
        """过滤和重排搜索结果.
        
        基于最高分进行相对阈值过滤，防止引入低质量无关文档。
        """
        if not docs_with_scores:
            return []

        # 基础打分与排序
        processed_results = []
        for doc, score in docs_with_scores:
            processed_results.append((doc, score))

        # 按得分降序排序
        processed_results.sort(key=lambda x: x[1], reverse=True)

        # 动态筛选：质量断层过滤
        top_score = processed_results[0][1]
        relative_ratio = 0.8  # 保留得分不低于最高分 80% 的结果

        quality_docs = []
        for doc, score in processed_results:
            if len(quality_docs) < self.config.search_k:
                if score >= (top_score * relative_ratio):
                    quality_docs.append(doc)
                else:
                    break

        logger.info(f"重排过滤完成：原始召回 {len(docs_with_scores)} 篇，最终保留优质文档 {len(quality_docs)} 篇")
        return quality_docs
