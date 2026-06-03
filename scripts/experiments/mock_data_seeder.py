# -*- coding: utf-8 -*-
"""Mock 语料种子脚本：直接向向量数据库中写入测试数据以验证切片和元数据注入。"""

import asyncio
import sys
from pathlib import Path
from loguru import logger

# 确保能找到 backend 包
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.core.config import get_config
from app.retrieval.embeddings import EmbeddingAdapter
from app.retrieval.vector_store import ChromaAdapter
from app.retrieval.document_processor import DocumentProcessor

class MockDocument:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata

def main():
    config = get_config()
    
    from langchain_community.embeddings import FakeEmbeddings
    embed_model = FakeEmbeddings(size=384)
    
    logger.info("2. 初始化 Chroma 向量库...")
    vector_store = ChromaAdapter(config, embed_model)
    if not vector_store.initialize():
        logger.error("向量库初始化失败")
        return
        
    logger.info("3. 准备 Mock 原始文档数据...")
    raw_docs = [
        MockDocument(
            page_content="苹果公司（Apple Inc.）是一家美国的跨国科技公司。它由史蒂夫·乔布斯等人创立，最著名的产品包括 iPhone、iPad 以及 Mac 电脑。近年来苹果大力发展自己的 M 系列芯片，性能表现极其优异。",
            metadata={"title": "苹果公司简介", "path": "科技/硅谷巨头", "source": "mock_test", "note_id": "mock_001"}
        ),
        MockDocument(
            page_content="香蕉是一种常见的水果。香蕉富含钾元素，非常适合运动后补充体力。世界上有很多种香蕉，但目前商业种植最广泛的是卡文迪什香蕉。",
            metadata={"title": "水果百百科：香蕉", "path": "生活/饮食", "source": "mock_test", "note_id": "mock_002"}
        ),
        MockDocument(
            page_content="Python 是一门广泛使用的高级编程语言。它支持面向对象、命令式和函数式编程范式。在 AI 领域，Python 占据了绝对的统治地位。",
            metadata={"title": "Python 编程语言", "path": "计算机/编程", "source": "mock_test", "note_id": "mock_003"}
        )
    ]
    
    logger.info("4. 触发 DocumentProcessor 进行文本切分和元数据注入...")
    processor = DocumentProcessor(config)
    chunks = processor.split_documents(raw_docs)
    
    for i, chunk in enumerate(chunks):
        logger.info(f"--- Chunk {i+1} ---")
        logger.info(f"Content: \n{chunk.page_content}")
        logger.info(f"Metadata: {chunk.metadata}")
        
    logger.info("5. 写入向量数据库...")
    vector_store.clear()  # 清空旧测试数据
    vector_store.add_documents(chunks)
    logger.info("数据注入完毕！")

if __name__ == "__main__":
    main()
