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
from app.core.knowledge_base import KnowledgeBase
from app.core.llm_service import LLMService
from app.core.qa_service import QAService
from app.core.security import mask_sensitive_data

# 配置日志脱敏
logger.add(lambda msg: None, filter=mask_sensitive_data)

# 获取配置
config = get_config()


# 设置镜像源
if config.hf_endpoint:
    os.environ["HF_ENDPOINT"] = config.hf_endpoint

# 初始化全局服务 (延迟到启动事件)
global_llm_service = None
global_knowledge_base = None
global_qa_service = None

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
    logger.info("正在初始化全局服务...")
    global global_llm_service, global_knowledge_base, global_qa_service

    try:
        # 使用 to_thread 异步化初始化耗时操作
        global_llm_service = await asyncio.to_thread(LLMService, config)
        global_knowledge_base = await asyncio.to_thread(KnowledgeBase, config)
        global_qa_service = await asyncio.to_thread(QAService, config, global_llm_service, global_knowledge_base)

        # 将全局服务添加到应用状态
        app.state.llm_service = global_llm_service
        app.state.knowledge_base = global_knowledge_base
        app.state.qa_service = global_qa_service

        logger.info("全局服务初始化完成")
    except Exception as e:
        logger.error(f"全局服务初始化失败: {e}")
        logger.exception("详细错误信息")

    logger.info("应用启动完成")
    if global_qa_service and hasattr(global_qa_service, "init_errors"):
        errors = global_qa_service.init_errors
        if errors:
            logger.warning("服务初始化存在以下错误:")
            for error in errors:
                logger.warning(f"  - {error}")
        else:
            logger.info("服务初始化成功")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件，确保资源正确释放."""
    logger.info("应用正在关闭，释放资源...")

    # 释放语言模型
    if hasattr(app.state, "llm_service") and app.state.llm_service:
        app.state.llm_service.cleanup()

    # 释放知识库
    if hasattr(app.state, "knowledge_base") and app.state.knowledge_base:
        app.state.knowledge_base.cleanup()

    logger.info("所有资源已释放，应用已安全关闭")


@app.get("/")
async def root():
    """根路径端点."""
    return {"message": "欢迎使用Trilium知识库智能体API"}


@app.get("/health")
async def health_check():
    """增强的健康检查端点，检查各组件状态."""
    health_status = {
        "status": "healthy",
        "components": {"llm": "unknown", "vector_db": "unknown", "trilium": "unknown"},
        "errors": []
    }

    # 检查 LLM
    if hasattr(app.state, "llm_service") and app.state.llm_service and app.state.llm_service.llm:
        health_status["components"]["llm"] = "available"
    else:
        health_status["components"]["llm"] = "unavailable"
        health_status["status"] = "degraded"

    # 检查向量数据库
    if hasattr(app.state, "knowledge_base") and app.state.knowledge_base and app.state.knowledge_base.vector_store:
        health_status["components"]["vector_db"] = "available"
    else:
        health_status["components"]["vector_db"] = "unavailable"
        health_status["status"] = "degraded"

    # 检查核心服务状态
    if hasattr(app.state, "qa_service") and app.state.qa_service:
        if hasattr(app.state.qa_service, "init_errors") and app.state.qa_service.init_errors:
            health_status["errors"] = app.state.qa_service.init_errors
            health_status["status"] = "degraded"
            
    # 如果两个核心组件都不可用，则认为系统不健康
    if health_status["components"]["llm"] == "unavailable" and health_status["components"]["vector_db"] == "unavailable":
        health_status["status"] = "unhealthy"

    return health_status


def check_and_download_models():
    """检查并下载必要的模型."""
    try:
        # 检查嵌入模型
        embedding_model_path = Path(config.embedding_model_local_path)
        if not embedding_model_path.exists():
            logger.warning(f"嵌入模型不存在: {embedding_model_path}")
            logger.info("请运行 'python scripts/download_models.py' 下载模型")
            logger.info("或者手动将模型文件放到指定路径")
            return False

        # 检查语言模型
        llm_model_path = Path(config.llm_model_path)
        if config.llm_model_type.lower() == "qwen":
            # 对于Qwen，我们检查模型目录
            if not llm_model_path.exists():
                logger.warning(f"Qwen模型不存在: {llm_model_path}")
                logger.info("请确保模型文件已下载到指定路径")
                return False
        else:
            # 对于GPT4All，我们检查具体文件
            if not llm_model_path.exists():
                logger.warning(f"语言模型不存在: {llm_model_path}")
                logger.info("请确保模型文件已下载到指定路径")
                return False

        logger.info("所有必需的离线模型均已就绪")
        return True
    except Exception as e:
        logger.error(f"检查模型时出错: {e}")
        return False


if __name__ == "__main__":
    # 检查模型
    logger.info("正在检查必需的离线模型...")
    if not check_and_download_models():
        logger.warning("模型检查失败，请检查上述错误信息。")
        logger.info("您仍然可以使用知识库搜索功能，但无法使用语言模型生成功能。")

    uvicorn.run(app="app.main:app", host="0.0.0.0", port=8000, reload=True)
