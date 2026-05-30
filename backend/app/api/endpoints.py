# -*- coding: utf-8 -*-
"""API endpoints for the Trilium Knowledge Agent."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_qa_service
from app.api.schemas import AnswerResponse, QuestionRequest
from app.core.config import get_config
from app.core.container import container
from app.core.security import verify_api_key
from app.services.qa_service import QAService

router = APIRouter()

@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    qa_service: QAService = Depends(get_qa_service),
    _token: str = Depends(verify_api_key),
) -> AnswerResponse:
    """Ask a question based on the knowledge base."""
    session_id = request.session_id or "default"
    result = await qa_service.ask(request.question, session_id=session_id)

    return AnswerResponse(answer=result["answer"], sources=result.get("sources", []))

@router.get("/status")
async def get_status(_token: str = Depends(verify_api_key)) -> dict[str, Any]:
    """Get the status of the knowledge agent."""
    config = get_config()
    
    status_info = {
        "status": "running",
        "trilium_base_url": config.trilium_base_url,
        "embedding_model": config.embedding_model,
        "initialization_errors": container.init_errors,
    }

    return status_info

@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    qa_service: QAService = Depends(get_qa_service),
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """Clear conversation history for a session."""
    cleared = await qa_service.session_manager.clear_session(session_id)
    if cleared:
        return {"status": "success", "message": f"Session {session_id} cleared"}
    return {"status": "success", "message": f"Session {session_id} not found or already cleared"}

@router.post("/sync")
async def sync_knowledge_base(
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """Sync the vector database with Trilium Notes (Placeholder)."""
    return {"status": "info", "message": "知识库同步已触发（目前仅作 API 占位，后端爬虫尚未接入）"}
