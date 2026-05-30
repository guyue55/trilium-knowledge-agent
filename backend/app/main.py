# -*- coding: utf-8 -*-
"""Trilium知识库智能体主应用入口."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.endpoints import router as api_router
from app.core.config import get_config
from app.core.container import container
from app.core.security import mask_sensitive_data
from app.llm.factory import LLMFactory
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager
from app.retrieval.embeddings import EmbeddingAdapter
from app.retrieval.bm25 import BM25StoreAdapter
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import ChromaAdapter

# 配置日志脱敏
logger.add(lambda msg: None, filter=mask_sensitive_data)

# 获取配置
config = get_config()

# 设置镜像源
if config.hf_endpoint:
    os.environ["HF_ENDPOINT"] = config.hf_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器：在启动时挂载组件，关闭时清理资源."""
    logger.info("正在初始化全局单例组件并注入 Container...")
    try:
        # 1. 实例化缓存与内存管理
        container.cache_manager = CacheManager(config)
        container.session_manager = SessionManager()

        # 2. 异步化初始化耗时模型组件
        try:
            container.llm_adapter = await asyncio.to_thread(LLMFactory.create_llm, config)
        except Exception as e:
            container.set_error(f"LLMFactory 创建异常: {e}")
        
        embedding_adapter = EmbeddingAdapter(config)
        try:
            await asyncio.to_thread(embedding_adapter.initialize)
            embed_model = embedding_adapter.get_model()
            if not embed_model:
                raise ValueError("Embedding 模型为空")
        except Exception as e:
            logger.warning(f"Embedding 加载失败: {e}，启用 FakeEmbeddings 进行降级模拟测试")
            from langchain_community.embeddings import FakeEmbeddings
            embed_model = FakeEmbeddings(size=384)
            container.set_error(f"Embedding 加载异常，已降级: {e}")
        
        container.vector_store = ChromaAdapter(config, embed_model)
        await asyncio.to_thread(container.vector_store.initialize)
        
        container.bm25_store = BM25StoreAdapter(config)
        
        container.reranker = Reranker(config)

        logger.info("全局组件装载完成")
    except Exception as e:
        container.set_error(f"全局服务初始化发生致命错误: {e}")
        logger.exception("详细错误信息")

    # ===============================
    # 让 FastAPI 服务在此处运行
    # ===============================
    yield
    
    # ===============================
    # 服务关闭后的资源清理逻辑
    # ===============================
    logger.info("应用正在关闭，释放 Container 资源...")
    container.cleanup()
    logger.info("应用已安全关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Trilium Knowledge Agent",
    description="一个基于FastAPI的应用，用于与Trilium Notes知识库进行交互，使用RAG技术。",
    version="0.1.0",
    lifespan=lifespan
)

# 添加CORS中间件
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "欢迎使用Trilium知识库智能体API"}


@app.get("/health")
async def health_check():
    """增强的健康检查端点."""
    health_status = {
        "status": "healthy",
        "components": {"llm": "unknown", "vector_db": "unknown", "reranker": "unknown"},
        "errors": container.init_errors
    }

    if container.llm_adapter and container.llm_adapter.get_langchain_llm():
        # 如果是 Mock，标记为 degraded
        if container.llm_adapter.__class__.__name__ == "MockLLMAdapter":
            health_status["components"]["llm"] = "degraded (mocked)"
            health_status["status"] = "degraded"
        else:
            health_status["components"]["llm"] = "available"
    else:
        health_status["components"]["llm"] = "unavailable"
        health_status["status"] = "degraded"

    if container.vector_store and container.vector_store.vector_store:
        health_status["components"]["vector_db"] = "available"
    else:
        health_status["components"]["vector_db"] = "unavailable"
        health_status["status"] = "degraded"

    if container.reranker:
        if not container.reranker._initialized:
            health_status["components"]["reranker"] = "pending_initialization"
        elif getattr(container.reranker, "_model", None) is not None:
            health_status["components"]["reranker"] = "advanced_cross_encoder"
        else:
            health_status["components"]["reranker"] = "basic_fallback"
            
    if health_status["components"]["llm"] == "unavailable" and health_status["components"]["vector_db"] == "unavailable":
        health_status["status"] = "unhealthy"

    return health_status


def check_and_download_models():
    """检查模型文件."""
    try:
        embedding_model_path = Path(config.embedding_model_local_path)
        if not embedding_model_path.exists():
            logger.warning(f"嵌入模型不存在: {embedding_model_path}")
            return False

        llm_model_path = Path(config.llm_model_path)
        if config.llm_model_type.lower() == "qwen":
            if not llm_model_path.exists():
                logger.warning(f"Qwen模型不存在: {llm_model_path}")
                return False
        else:
            if not llm_model_path.exists():
                logger.warning(f"语言模型不存在: {llm_model_path}")
                return False

        return True
    except Exception as e:
        logger.error(f"检查模型出错: {e}")
        return False


if __name__ == "__main__":
    logger.info("正在检查必需的离线模型...")
    if not check_and_download_models():
        logger.warning("模型检查失败。您仍然可以使用知识库搜索，但无法生成答案。")

    uvicorn.run(app="app.main:app", host="0.0.0.0", port=8000, reload=True)
