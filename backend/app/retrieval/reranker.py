# -*- coding: utf-8 -*-
"""重排器 (Reranker) 适配器."""

from typing import Any, List, Tuple
from loguru import logger

from app.core.config import Config
from app.retrieval.document import Document

class Reranker:
    """基于 FastEmbed 的交叉编码器重排封装."""

    def __init__(self, config: Config):
        self.config = config
        self._model = None
        self._initialized = False

    def initialize(self) -> bool:
        if not self.config.use_reranker:
            logger.info("配置指定不使用重排器 (use_reranker=false)")
            return True

        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            
            # 优先从配置中读取重排器模型及已经自适应绝对化归一化的物理路径
            model_name = self.config.reranker_model or "BAAI/bge-reranker-base"
            cache_dir = self.config.reranker_model_local_path
            
            logger.info(f"正在加载 FastEmbed 重排模型: {model_name} (缓存目录: {cache_dir})")
            
            self._model = TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)
            self._initialized = True
            logger.info("重排器加载成功")
            return True
        except Exception as e:
            logger.warning(f"无法加载重排器，将降级到基线检索结果: {e}")
            self._model = None
            self._initialized = False
            return False

    def rerank_and_filter(
        self, docs_with_scores: List[Tuple[Document, float]], query: str
    ) -> List[Document]:
        """对检索结果进行重排并应用阈值过滤 (兼容最新 FastEmbed TextCrossEncoder)."""
        if not docs_with_scores:
            return []

        # 降级逻辑
        if not self._model or not self.config.use_reranker:
            # 简单去重并按照原始分数排序
            docs_with_scores.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, _ in docs_with_scores[:self.config.search_k]]

        docs = [doc for doc, _ in docs_with_scores]
        texts = [doc.page_content for doc in docs]
        
        try:
            # 最新 FastEmbed TextCrossEncoder.rerank 直接返回 float 类型分数列表
            scores = list(self._model.rerank(query, texts))
            
            # 使用 zip 关联文档和分数，并按照分数进行降序重排
            paired_docs = list(zip(docs, scores))
            paired_docs.sort(key=lambda x: x[1], reverse=True)
            
            filtered_docs = []
            for doc, score in paired_docs:
                # 过滤不符合重排阈值的文档 (Xenova / BGE 的输出可能是实数)
                if score >= self.config.reranker_threshold:
                    filtered_docs.append(doc)
                    
            # 最终截断到 search_k
            return filtered_docs[:self.config.search_k]
            
        except Exception as e:
            logger.error(f"重排过程中发生异常: {e}，回退到原始结果")
            return [doc for doc, _ in docs_with_scores[:self.config.search_k]]
