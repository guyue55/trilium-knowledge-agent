# -*- coding: utf-8 -*-
"""Trilium知识库智能体主应用入口."""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.endpoints import router as api_router
from app.core.config import get_config
from app.core.llm_service import LLMService
from app.core.knowledge_base import KnowledgeBase
from app.core.qa_service import QAService

# 获取配置
config = get_config()

# 设置镜像源
if config.hf_endpoint:
    os.environ['HF_ENDPOINT'] = config.hf_endpoint

# 初始化全局服务
print("正在初始化全局服务...")
global_llm_service = None
global_knowledge_base = None
global_qa_service = None

try:
    global_llm_service = LLMService(config)
    global_knowledge_base = KnowledgeBase(config)
    global_qa_service = QAService(config, global_llm_service, global_knowledge_base)
    print("全局服务初始化完成")
except Exception as e:
    print(f"全局服务初始化失败: {e}")
    import traceback
    traceback.print_exc()

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

# 将全局服务添加到应用状态
if global_llm_service:
    app.state.llm_service = global_llm_service
if global_knowledge_base:
    app.state.knowledge_base = global_knowledge_base
if global_qa_service:
    app.state.qa_service = global_qa_service

# 包含API路由
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """应用启动事件."""
    print("应用启动完成")
    if global_qa_service and hasattr(global_qa_service, 'init_errors'):
        errors = global_qa_service.init_errors
        if errors:
            print("服务初始化存在以下错误:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("服务初始化成功")


@app.get("/")
async def root():
    """根路径端点."""
    return {"message": "欢迎使用Trilium知识库智能体API"}


@app.get("/health")
async def health_check():
    """健康检查端点."""
    return {"status": "healthy"}


def check_and_download_models():
    """检查并下载必要的模型."""
    try:
        # 检查嵌入模型
        embedding_model_path = Path(config.embedding_model_local_path)
        if not embedding_model_path.exists():
            print(f"警告: 嵌入模型不存在: {embedding_model_path}")
            print("请运行 'python scripts/download_models.py' 下载模型")
            print("或者手动将模型文件放到指定路径")
            return False
        
        # 检查语言模型
        llm_model_path = Path(config.llm_model_path)
        if config.llm_model_type.lower() == "qwen":
            # 对于Qwen，我们检查模型目录
            if not llm_model_path.exists():
                print(f"警告: Qwen模型不存在: {llm_model_path}")
                print("请确保模型文件已下载到指定路径")
                return False
        else:
            # 对于GPT4All，我们检查具体文件
            if not llm_model_path.exists():
                print(f"警告: 语言模型不存在: {llm_model_path}")
                print("请确保模型文件已下载到指定路径")
                return False
            
        print("所有必需的离线模型均已就绪")
        return True
    except Exception as e:
        print(f"检查模型时出错: {e}")
        return False


if __name__ == "__main__":
    # 检查模型
    print("正在检查必需的离线模型...")
    if not check_and_download_models():
        print("模型检查失败，请检查上述错误信息。")
        print("您仍然可以使用知识库搜索功能，但无法使用语言模型生成功能。")
    
    uvicorn.run(
        app="app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )