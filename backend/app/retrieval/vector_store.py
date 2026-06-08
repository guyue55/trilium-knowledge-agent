# -*- coding: utf-8 -*-
"""向量库与混合检索适配器 (LanceDB)."""

import os
import threading
import asyncio
import inspect
from typing import Any, List, Tuple, Dict
from loguru import logger
import lancedb
from lancedb.pydantic import Vector, LanceModel

from app.core.config import Config
from app.retrieval.document import Document
from app.retrieval.embeddings import EmbeddingAdapter

class VectorStoreAdapter:
    """LanceDB 适配器实现 (原生支持混合检索 Hybrid Search)."""

    def __init__(self, config: Config, embedding_adapter: EmbeddingAdapter):
        self.config = config
        self.embedding_adapter = embedding_adapter
        self.db = None
        self.table = None
        self.table_name = "trilium_notes"
        self._db_lock = threading.Lock()
        # Ensure the vector db directory exists
        os.makedirs(self.config.vector_db_dir, exist_ok=True)

    def initialize(self) -> bool:
        if not self.embedding_adapter or not self.embedding_adapter.get_model():
            logger.error("Embedding 模型为空，LanceDB 无法初始化")
            return False
            
        try:
            # 初始化 LanceDB 连接
            self.db = lancedb.connect(self.config.vector_db_dir)
            
            # 使用 Dummy 测试获取维度大小
            dummy_vec = self.embedding_adapter.embed_query("test")
            dim = len(dummy_vec) if dummy_vec else 384
            
            # 使用动态生成 Schema (适配不同的 metadata 和维度)
            from pyarrow import schema, string, float32, list_, int32
            self.schema = schema([
                ("id", string()),
                ("vector", list_(float32(), dim)),
                ("text", string()),
                ("note_id", string()),
                ("title", string()),
                ("source", string()),
                ("path", string()),
                ("chunk_index", int32()),
            ])

            if self.table_name in self.db.table_names():
                self.table = self.db.open_table(self.table_name)
                logger.info(f"LanceDB 加载已有表 [{self.table_name}] 成功")
            else:
                # 创建新表
                self.table = self.db.create_table(self.table_name, schema=self.schema)
                logger.info(f"LanceDB 创建新表 [{self.table_name}] 成功，维度: {dim}")
                
            # 预热 jieba 中文分词模型，避免用户第一条请求因延迟加载而产生 2s+ 的拖拉卡顿
            try:
                import jieba
                jieba.initialize()
                logger.info("Jieba 中文分词模型预载热启动完成")
            except Exception as jieba_pre_e:
                logger.warning(f"预载 Jieba 分词出错 (可安全忽略): {jieba_pre_e}")
                
            return True
        except Exception as e:
            logger.error(f"LanceDB 初始化失败: {e}")
            return False

    def clear(self) -> None:
        if not self.db:
            return
        try:
            logger.info("正在清空 LanceDB 数据库...")
            with self._db_lock:
                if self.table_name in self.db.table_names():
                    self.db.drop_table(self.table_name)
                self.table = self.db.create_table(self.table_name, schema=self.schema)
            logger.info("LanceDB 数据库清空完毕")
        except Exception as e:
            logger.error(f"清空 LanceDB 时出错: {e}")

    def add_documents(self, documents: List[Document]) -> None:
        if self.table is None or not documents:
            return

        total_docs = len(documents)
        batch_size = self.config.vector_db_batch_size

        try:
            for i in range(0, total_docs, batch_size):
                batch = documents[i : i + batch_size]
                current_batch = i // batch_size + 1
                total_batches = (total_docs + batch_size - 1) // batch_size
                
                logger.info(f"添加文档批次 {current_batch}/{total_batches}...")
                
                texts = [doc.page_content for doc in batch]
                vectors = self.embedding_adapter.embed_documents(texts)
                
                data = []
                for j, doc in enumerate(batch):
                    if j >= len(vectors):
                        continue
                        
                    meta = doc.metadata or {}
                    # 构建 LanceDB 记录
                    record = {
                        "id": f"{meta.get('note_id', 'unknown')}_{meta.get('chunk_index', j)}_{i+j}",
                        "vector": vectors[j],
                        "text": doc.page_content,
                        "note_id": meta.get("note_id", ""),
                        "title": meta.get("title", ""),
                        "source": meta.get("source", ""),
                        "path": meta.get("path", ""),
                        "chunk_index": int(meta.get("chunk_index", 0))
                    }
                    data.append(record)
                    
                if data:
                    with self._db_lock:
                        self.table.add(data)
                        
            # 构建全文索引以便进行 hybrid search
            with self._db_lock:
                try:
                    self.table.create_fts_index("text", replace=True)
                    logger.info("LanceDB 全文检索 (FTS) 索引更新成功")
                except Exception as fts_e:
                    logger.warning(f"LanceDB FTS 索引创建跳过 (可能因为数据量太小或已存在): {fts_e}")
                    
        except Exception as e:
            logger.error(f"添加文档到 LanceDB 失败: {e}")

    async def similarity_search_with_scores(self, query: str, k: int = 5, score_threshold: float = 0.0) -> List[Tuple[Document, float]]:
        """执行黄金标准应用层 RRF 混合搜索 (纯向量语义搜索 + FTS/BM25 精准全文检索)."""
        if self.table is None:
            return []
            
        try:
            # 1. 异步化向量化查询，释放主线程 CPU 阻塞
            query_vector = await asyncio.to_thread(self.embedding_adapter.embed_query, query)
            if not query_vector:
                return []
                
            # 2. 预备 FTS 全文分词 Query，同样将 jieba 分词包装在独立线程中避免阻塞
            fts_query = query
            import re
            if re.search(r"[\u4e00-\u9fa5]", query):
                try:
                    import jieba
                    def _get_jieba_words():
                        words = list(jieba.cut_for_search(query))
                        return " ".join(words) if words else query
                    fts_query = await asyncio.to_thread(_get_jieba_words)
                    logger.debug(f"FTS 中文分词增强：原 Query = '{query}' -> 分词 Query = '{fts_query}'")
                except Exception as jieba_e:
                    logger.warning(f"Jieba 分词失败，回退到原始全文搜索: {jieba_e}")

            # 3. 定义两路独立检索的同步包装闭包，由 asyncio.to_thread 投递至多核子线程并发物理执行
            def _vector_search_sync():
                try:
                    return self.table.search(query_vector).limit(k * 2).to_list()
                except Exception as e:
                    logger.warning(f"向量路检索失败: {e}")
                    return []

            def _fts_search_sync():
                try:
                    return self.table.search(fts_query, query_type="fts").limit(k * 2).to_list()
                except Exception as e:
                    # 刚启动或无数据时报错属正常情况，优雅捕获并记录 debug
                    logger.debug(f"FTS 全文路检索跳过或不可用 (可能因为数据库为空或索引未建立): {e}")
                    return []

            # 4. 协程并发双路并行检索：突破 GIL 锁束缚，完美调动 LanceDB/Rust 底层物理多核性能
            vector_task = asyncio.to_thread(_vector_search_sync)
            fts_task = asyncio.to_thread(_fts_search_sync)
            
            vector_candidates, fts_candidates = await asyncio.gather(vector_task, fts_task)

            # 5. 倒数排名融合 (Reciprocal Rank Fusion)
            # 常数 C 设为 60.0 (业界公认数学性能最均衡参数)
            C = 60.0
            rrf_scores = {}
            doc_map = {}

            # 融合向量候选
            for rank, item in enumerate(vector_candidates, 1):
                doc_id = item.get("id")
                if doc_id:
                    doc_map[doc_id] = item
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (C + rank))

            # 融合全文候选
            for rank, item in enumerate(fts_candidates, 1):
                doc_id = item.get("id")
                if doc_id:
                    doc_map[doc_id] = item
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (C + rank))

            # 若没有任何候选结果，直接返回空
            if not rrf_scores:
                logger.debug("混合检索无任何候选召回结果")
                return []

            # 按照 RRF 合并分降序排列，取 Top k
            sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:k]
            logger.debug(f"RRF 双路召回融合完毕，共召回 {len(rrf_scores)} 个去重候选，取前 {len(sorted_candidates)} 个进行后续重排。")

            docs_with_scores = []
            for doc_id, rrf_val in sorted_candidates:
                r = doc_map[doc_id]
                
                # 归一化综合检索相关度评分 (映射到大约 [0.1, 0.99] 的直观浮点数，便于阈值过滤与调试展现)
                # 两路第 1 名的最大 RRF 值大约为 2/61 = 0.0328，我们乘以 30 来映射到 1.0 的尺度上
                score = min(0.99, max(0.01, rrf_val * 30.0))
                
                if score < score_threshold:
                    continue
                    
                meta = {
                    "note_id": r.get("note_id", ""),
                    "title": r.get("title", ""),
                    "source": r.get("source", ""),
                    "path": r.get("path", ""),
                    "chunk_index": r.get("chunk_index", 0)
                }
                
                doc = Document(page_content=r.get("text", ""), metadata=meta)
                docs_with_scores.append((doc, score))
                
            return docs_with_scores
            
        except Exception as e:
            logger.error(f"RRF 混合搜索执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
