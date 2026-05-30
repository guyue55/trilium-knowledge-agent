# -*- coding: utf-8 -*-
"""BM25 稀疏检索模块."""

import os
import pickle
from typing import Any, List

import jieba
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from loguru import logger

from app.core.config import Config


class BM25StoreAdapter:
    """管理 BM25 索引的持久化与检索."""

    def __init__(self, config: Config):
        self.config = config
        self.retriever: BM25Retriever | None = None
        
        # 确保向量库目录存在
        os.makedirs(self.config.vector_db_dir, exist_ok=True)
        self.persist_path = os.path.join(self.config.vector_db_dir, "bm25_store.pkl")
        self.initialize()

    def initialize(self) -> bool:
        """从磁盘加载现有的 BM25 索引."""
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, "rb") as f:
                    self.retriever = pickle.load(f)
                logger.info("BM25 索引从磁盘加载成功")
                return True
            except Exception as e:
                logger.error(f"加载 BM25 索引失败: {e}")
                self.retriever = None
        else:
            logger.info("本地未发现 BM25 索引，等待同步生成")
            
        return False

    def build_and_save(self, documents: List[Document]) -> None:
        """从文档重新构建并持久化 BM25 索引."""
        if not documents:
            logger.warning("传入的文档为空，跳过 BM25 构建")
            return
            
        logger.info(f"开始使用 {len(documents)} 篇文档构建 BM25 索引...")
        try:
            # 采用结巴分词作为 BM25 的底层分词器
            def jieba_tokenizer(text: str) -> List[str]:
                return list(jieba.cut_for_search(text))

            self.retriever = BM25Retriever.from_documents(
                documents, 
                preprocess_func=jieba_tokenizer
            )
            # 配置默认的 k 值 (BM25 独立召回数量，通常比 vector_store 大一点)
            self.retriever.k = self.config.search_k * 2
            
            with open(self.persist_path, "wb") as f:
                pickle.dump(self.retriever, f)
            logger.info("BM25 索引构建并持久化成功")
        except Exception as e:
            logger.error(f"构建 BM25 索引失败: {e}")

    def clear(self) -> None:
        """清空 BM25 索引."""
        self.retriever = None
        if os.path.exists(self.persist_path):
            try:
                os.remove(self.persist_path)
                logger.info("BM25 索引文件已删除")
            except OSError as e:
                logger.error(f"删除 BM25 索引失败: {e}")

    def retrieve(self, query: str, k: int = 5) -> List[Any]:
        """执行 BM25 检索."""
        if not self.retriever:
            return []
        
        try:
            # 临时修改检索数量
            original_k = self.retriever.k
            self.retriever.k = k
            docs = self.retriever.invoke(query)
            self.retriever.k = original_k
            return docs
        except Exception as e:
            logger.error(f"BM25 检索失败: {e}")
            return []
