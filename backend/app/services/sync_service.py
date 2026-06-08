# -*- coding: utf-8 -*-
"""知识库同步服务.

负责协调 TriliumCrawler, DocumentProcessor, 和 VectorStore，实现后台数据构建。
"""

import asyncio
from loguru import logger

from app.core.config import Config
from app.retrieval.vector_store import VectorStoreAdapter
from app.trilium.client import TriliumClient
from app.trilium.crawler import TriliumCrawler
from app.retrieval.document_processor import DocumentProcessor
from app.retrieval.document import Document

class SyncService:
    """管理同步作业的领域服务."""
    
    def __init__(self, config: Config, vector_store: VectorStoreAdapter):
        self.config = config
        self.vector_store = vector_store
        self.processor = DocumentProcessor(config)
        
    async def run_sync_job(self) -> None:
        """执行知识库全量同步作业."""
        logger.info("开始执行知识库后台同步作业...")
        
        try:
            # 1. 异步 Offload 连接 Trilium，防握手卡死事件循环
            client = await asyncio.to_thread(TriliumClient, self.config.trilium_base_url, self.config.trilium_token)
            connected = await asyncio.to_thread(client.is_connected)
            if not connected:
                logger.error("SyncService: Trilium 客户端连接失败，终止同步。")
                return
            
            # 2. 爬取原始文档
            crawler = TriliumCrawler(self.config, client)
            # crawler 的 load_documents 是同步阻塞函数，用 to_thread 包装
            raw_docs = await asyncio.to_thread(crawler.load_documents)
            
            if not raw_docs:
                logger.warning("SyncService: 爬取到 0 篇文档。")
                return
            
            logger.info(f"SyncService: 成功爬取 {len(raw_docs)} 篇原始文档，开始切分...")
            
            # 3. 组装 Document 并切分
            domain_docs = [
                Document(page_content=d["content"], metadata={k: v for k, v in d.items() if k != "content"}) 
                for d in raw_docs
            ]
            chunks = self.processor.split_documents(domain_docs)
            
            logger.info(f"SyncService: 文档切分完毕，共 {len(chunks)} 个碎片切片。")
            
            # 4. 更新向量库 (LanceDB)
            logger.info("SyncService: 开始清空旧知识库...")
            await asyncio.to_thread(self.vector_store.clear)
            
            logger.info(f"SyncService: 开始将 {len(chunks)} 个切片灌入知识库...")
            await asyncio.to_thread(self.vector_store.add_documents, chunks)
            
            logger.info("🎉 知识库同步作业圆满完成！")
            
        except Exception as e:
            logger.exception(f"知识库后台同步作业发生严重异常: {e}")
