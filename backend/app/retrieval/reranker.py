import os
from typing import Any, List

from loguru import logger

from app.core.config import Config


class Reranker:
    """实现对召回文档的质量筛选（宁缺毋滥）和排序."""

    def __init__(self, config: Config):
        self.config = config
        self._model = None
        self._initialized = False

    def _initialize(self):
        """延迟初始化重排模型."""
        if self._initialized:
            return

        if not self.config.use_reranker:
            logger.info("未启用重排模型，将使用基础过滤规则。")
            self._initialized = True
            return

        try:
            # 优先尝试本地路径，否则使用 HF hub 名称
            model_name_or_path = self.config.reranker_model_local_path
            if not os.path.exists(model_name_or_path):
                logger.warning(f"本地重排模型不存在: {model_name_or_path}，尝试从 HuggingFace Hub 下载")
                model_name_or_path = self.config.reranker_model

            from FlagEmbedding import FlagReranker
            import torch
            logger.info(f"正在加载重排模型 (FlagReranker): {model_name_or_path}")
            
            # 动态检测硬件环境，非 NVIDIA 显卡或纯 CPU 强制关闭 fp16，防止 PyTorch 报错
            use_fp16 = torch.cuda.is_available()
            if not use_fp16:
                logger.info("未检测到 CUDA 环境，将禁用 fp16 混合精度以保证兼容性")
                
            self._model = FlagReranker(model_name_or_path, use_fp16=use_fp16)
            logger.info("重排模型加载成功")
        except ImportError:
            logger.warning("未安装 FlagEmbedding，无法使用高级重排功能，将降级为基础过滤规则。请运行: pip install FlagEmbedding")
        except Exception as e:
            logger.error(f"加载重排模型失败: {e}，将降级为基础过滤规则。")

        self._initialized = True

    def rerank_and_filter(self, docs_with_scores: List[tuple[Any, float]], question: str) -> List[Any]:
        """过滤和重排搜索结果."""
        if not docs_with_scores:
            return []

        self._initialize()

        if self._model:
            return self._advanced_rerank(docs_with_scores, question)
        else:
            return self._basic_filter(docs_with_scores)

    def _advanced_rerank(self, docs_with_scores: List[tuple[Any, float]], question: str) -> List[Any]:
        """使用 Cross-Encoder 模型进行精准重排."""
        docs = [doc for doc, _ in docs_with_scores]
        # 构建文本对: (Query, Document_Content)
        sentence_pairs = [[question, doc.page_content] for doc in docs]
        
        try:
            # 打分，越高越相关
            scores = self._model.compute_score(sentence_pairs, normalize=True)
            
            # 如果只有单个结果，compute_score 返回的是浮点数而不是列表
            if isinstance(scores, float):
                scores = [scores]
            
            # 将文档与得分组合并排序
            doc_score_pairs = list(zip(docs, scores))
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
            
            # 选择 Top-K
            top_k = min(self.config.reranker_top_k, len(doc_score_pairs))
            quality_docs = [doc for doc, score in doc_score_pairs[:top_k]]
            
            logger.info(f"Cross-Encoder 重排完成：原始召回 {len(docs_with_scores)} 篇，最终保留优质文档 {len(quality_docs)} 篇 (Top Score: {doc_score_pairs[0][1]:.4f})")
            return quality_docs
            
        except Exception as e:
            logger.error(f"高级重排执行失败: {e}，回退至基础过滤")
            return self._basic_filter(docs_with_scores)

    def _basic_filter(self, docs_with_scores: List[tuple[Any, float]]) -> List[Any]:
        """基于最高分进行相对阈值过滤，防止引入低质量无关文档。"""
        # 基础打分与排序
        processed_results = []
        for doc, score in docs_with_scores:
            processed_results.append((doc, score))

        # 按得分降序排序 (如果是距离则应为升序，这里假设为相似度得分)
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

        logger.info(f"基础重排过滤完成：原始召回 {len(docs_with_scores)} 篇，最终保留优质文档 {len(quality_docs)} 篇")
        return quality_docs
