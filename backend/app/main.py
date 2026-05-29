# -*- coding: utf-8 -*-
"""Trilium知识库智能体主应用入口."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.endpoints import router as api_router
from app.core.config import get_config
from app.core.security import mask_sensitive_data
from app.llm.factory import LLMFactory
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager
from app.qa.pipeline import QAPipeline
from app.retrieval.embeddings import EmbeddingAdapter
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import ChromaAdapter

# 配置日志脱敏
logger.add(lambda msg: None, filter=mask_sensitive_data)

# 获取配置
config = get_config()


# 设置镜像源
if config.hf_endpoint:
    os.environ["HF_ENDPOINT"] = config.hf_endpoint

# 创建FastAPI应用
app = FastAPI(
    title="Trilium Knowledge Agent",
    description="一个基于FastAPI的应用，用于与Trilium Notes知识库进行交互，使用RAG技术。",
    version="0.1.0",
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


@app.on_event("startup")
async def startup_event():
    """应用启动事件."""
    logger.info("正在初始化全局组件...")

    try:
        # 1. 实例化缓存与内存管理
        cache_manager = CacheManager(config)
        session_manager = SessionManager()

        # 2. 异步化初始化耗时模型组件
        llm_adapter = await asyncio.to_thread(LLMFactory.create_llm, config)
        
        embedding_adapter = EmbeddingAdapter(config)
        await asyncio.to_thread(embedding_adapter.initialize)
        
        vector_store = ChromaAdapter(config, embedding_adapter.get_model())
        await asyncio.to_thread(vector_store.initialize)
        
        reranker = Reranker(config)

        # 3. 组装 Pipeline
        qa_pipeline = QAPipeline(
            config=config,
            llm_adapter=llm_adapter,
            vector_store=vector_store,
            reranker=reranker,
            cache_manager=cache_manager,
            session_manager=session_manager
        )

        # 挂载到 app.state
        app.state.llm_adapter = llm_adapter
        app.state.vector_store = vector_store
        app.state.qa_pipeline = qa_pipeline

        logger.info("全局组件初始化完成")
    except Exception as e:
        logger.error(f"全局服务初始化失败: {e}")
        logger.exception("详细错误信息")

    logger.info("应用启动完成")
    if hasattr(app.state, "qa_pipeline") and app.state.qa_pipeline.init_errors:
        errors = app.state.qa_pipeline.init_errors
        logger.warning("服务初始化存在以下错误:")
        for error in errors:
            logger.warning(f"  - {error}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件."""
    logger.info("应用正在关闭，释放资源...")
    if hasattr(app.state, "llm_adapter") and app.state.llm_adapter:
        app.state.llm_adapter.cleanup()
    logger.info("应用已安全关闭")


@app.get("/")
async def root():
    return {"message": "欢迎使用Trilium知识库智能体API"}


@app.get("/health")
async def health_check():
    """增强的健康检查端点."""
    health_status = {
        "status": "healthy",
        "components": {"llm": "unknown", "vector_db": "unknown", "reranker": "unknown"},
        "errors": []
    }

    if hasattr(app.state, "llm_adapter") and app.state.llm_adapter and app.state.llm_adapter.get_langchain_llm():
        health_status["components"]["llm"] = "available"
    else:
        health_status["components"]["llm"] = "unavailable"
        health_status["status"] = "degraded"

    if hasattr(app.state, "vector_store") and app.state.vector_store and app.state.vector_store.vector_store:
        health_status["components"]["vector_db"] = "available"
    else:
        health_status["components"]["vector_db"] = "unavailable"
        health_status["status"] = "degraded"

    if hasattr(app.state, "qa_pipeline"):
        # 检查重排器状态
        if hasattr(app.state.qa_pipeline, "reranker"):
            reranker = app.state.qa_pipeline.reranker
            if not reranker._initialized:
                health_status["components"]["reranker"] = "pending_initialization"
            elif reranker._model is not None:
                health_status["components"]["reranker"] = "advanced_cross_encoder"
            else:
                health_status["components"]["reranker"] = "basic_fallback"

        if app.state.qa_pipeline.init_errors:
            health_status["errors"] = app.state.qa_pipeline.init_errors
            health_status["status"] = "degraded"
            
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
