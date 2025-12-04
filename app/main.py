# -*- coding: utf-8 -*-
"""Trilium知识库智能体主应用入口."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.endpoints import router as api_router
from app.core.config import get_config

# 获取配置
config = get_config()

# 创建FastAPI应用
app = FastAPI(
    title="Trilium Knowledge Agent",
    description="一个基于FastAPI的应用，用于与Trilium Notes知识库进行交互，使用RAG技术。",
    version="0.1.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径端点."""
    return {"message": "欢迎使用Trilium知识库智能体API"}


@app.get("/health")
async def health_check():
    """健康检查端点."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        app="app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )