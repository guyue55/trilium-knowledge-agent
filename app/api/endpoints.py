# -*- coding: utf-8 -*-
"""API endpoints for the Trilium Knowledge Agent."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from loguru import logger

from app.api.schemas import AnswerResponse, QuestionRequest
from app.core.config import get_config
from app.core.security import verify_api_key

router = APIRouter()


def get_qa_pipeline(request: Request):
    """获取问答管道实例."""
    if hasattr(request.app.state, "qa_pipeline") and request.app.state.qa_pipeline:
        return request.app.state.qa_pipeline

    # 后备方案不建议在请求时同步初始化所有模块，这里直接抛出异常
    logger.error("全局 qa_pipeline 未初始化")
    raise RuntimeError("Service not initialized")


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    qa_pipeline = Depends(get_qa_pipeline),
    _token: str = Depends(verify_api_key),
) -> AnswerResponse:
    """Ask a question based on the knowledge base."""
    session_id = request.session_id or "default"
    result = await qa_pipeline.ask(request.question, session_id=session_id)

    return AnswerResponse(answer=result["answer"], sources=result.get("sources", []))


@router.get("/status")
async def get_status(request: Request, _token: str = Depends(verify_api_key)) -> dict[str, Any]:
    """Get the status of the knowledge agent."""
    config = get_config()
    
    status_info = {
        "status": "running",
        "trilium_base_url": config.trilium_base_url,
        "embedding_model": config.embedding_model,
        "initialization_errors": [],
    }

    if hasattr(request.app.state, "qa_pipeline") and request.app.state.qa_pipeline:
        if hasattr(request.app.state.qa_pipeline, "init_errors") and request.app.state.qa_pipeline.init_errors:
            status_info["initialization_errors"] = request.app.state.qa_pipeline.init_errors

    return status_info
