# -*- coding: utf-8 -*-
"""用于更新知识库的脚本."""

import os
import sys

# 获取项目根目录 (scripts/data 的上一级的上一级)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 将 backend 目录添加到路径中
sys.path.append(os.path.join(PROJECT_ROOT, "backend"))

from langchain.docstore.document import Document
from loguru import logger

from app.core.config import get_config
from app.retrieval.document_processor import DocumentProcessor
from app.retrieval.embeddings import EmbeddingAdapter
from app.retrieval.vector_store import ChromaAdapter
from app.trilium.client import TriliumClient
from app.trilium.crawler import TriliumCrawler


def update_knowledge_base():
    """使用来自Trilium的最新文档更新知识库."""
    logger.info("正在更新知识库...")

    config = get_config()
    config.depth = int(os.getenv("TRILIUM_EXPORT_DEPTH", 20))
    config.limit = int(os.getenv("TRILIUM_EXPORT_LIMIT", 10000))
    logger.info(f"已设置文档获取限制为: {config.limit}, 深度: {config.depth}")

    # 1. 抓取原始文档
    logger.info("正在从Trilium加载文档...")
    client = TriliumClient(config.trilium_base_url, config.trilium_token)
    crawler = TriliumCrawler(config, client)
    raw_documents = crawler.load_documents()

    documents = []
    for doc in raw_documents:
        title = doc.get("title", "未知标题")
        if not title or title.strip() == "":
            title = "未知标题"

        document = Document(
            page_content=doc.get("content", ""),
            metadata={
                "title": title,
                "note_id": doc.get("note_id", ""),
                "source": f"trilium:{doc.get('note_id', '')}",
            },
        )
        documents.append(document)

    logger.info(f"已从 Trilium 加载 {len(documents)} 个文档")

    if len(documents) > 0:
        # 2. 文档切分
        logger.info("正在进行文档切分...")
        processor = DocumentProcessor(config)
        split_docs = processor.split_documents(documents)
        logger.info(f"文档切分完毕，共生成 {len(split_docs)} 个文本块")

        # 3. 初始化向量库
        logger.info("正在初始化向量存储...")
        embedding_adapter = EmbeddingAdapter(config)
        embedding_adapter.initialize()
        
        vector_store = ChromaAdapter(config, embedding_adapter.get_model())
        vector_store.initialize()

        # 4. 清空并全量更新
        logger.info("正在清空旧的向量数据...")
        vector_store.clear()

        logger.info("正在添加新向量数据...")
        vector_store.add_documents(split_docs)

        logger.info("知识库更新成功！")
    else:
        logger.warning("未加载到任何文档，跳过更新。")
        
    client.cleanup()


if __name__ == "__main__":
    update_knowledge_base()
