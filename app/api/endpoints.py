# -*- coding: utf-8 -*-
"""API endpoints for the Trilium Knowledge Agent."""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any

from app.api.schemas import QuestionRequest, AnswerResponse
from app.core.config import get_config
from app.core.llm_service import LLMService
from app.core.knowledge_base import KnowledgeBase
from app.core.qa_service import QAService

router = APIRouter()


def get_qa_service(request: Request):
    """获取问答服务实例."""
    # 从应用状态中获取全局服务实例
    if hasattr(request.app.state, 'qa_service') and request.app.state.qa_service:
        return request.app.state.qa_service
    
    # 如果没有全局服务实例，创建新的（后备方案）
    config = get_config()
    llm_service = LLMService(config)
    knowledge_base = KnowledgeBase(config)
    qa_service = QAService(config, llm_service, knowledge_base)
    return qa_service


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest, qa_service: QAService = Depends(get_qa_service)) -> AnswerResponse:
    """Ask a question based on the knowledge base.
    
    Args:
        request: The question request.
        qa_service: The QA service instance.
        
    Returns:
        The answer response with sources.
    """
    # 实现实际的问答逻辑
    result = qa_service.ask_question(request.question)
    
    # 确保返回的数据符合AnswerResponse模型
    return AnswerResponse(
        answer=result["answer"],
        sources=result.get("sources", [])
    )


@router.get("/status")
async def get_status(request: Request) -> Dict[str, Any]:
    """Get the status of the knowledge agent.
    
    Returns:
        Status information.
    """
    config = get_config()
    qa_service = get_qa_service(request)
    
    status_info = {
        "status": "running",
        "trilium_base_url": config.trilium_base_url,
        "embedding_model": config.embedding_model,
        "initialization_errors": []
    }
    
    # 添加初始化错误信息（如果有）
    if hasattr(qa_service, 'init_errors') and qa_service.init_errors:
        status_info["initialization_errors"] = qa_service.init_errors
    
    return status_info