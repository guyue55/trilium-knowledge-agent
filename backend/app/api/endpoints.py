# -*- coding: utf-8 -*-
"""API endpoints for the Trilium Knowledge Agent."""

from __future__ import annotations

from typing import Any
import json
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.api.deps import get_qa_service, get_config, get_vector_store
from app.api.schemas import AnswerResponse, QuestionRequest
from app.core.config import Config
from app.core.container import container
from app.core.security import verify_api_key
from app.retrieval.bm25 import BM25StoreAdapter
from app.retrieval.vector_store import VectorStoreAdapter
from app.services.qa_service import QAService
from app.services.sync_service import SyncService

def get_bm25_store() -> BM25StoreAdapter:
    return container.bm25_store

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

@router.post("/ask_stream")
async def ask_question_stream(
    request: QuestionRequest,
    qa_service: QAService = Depends(get_qa_service),
    _token: str = Depends(verify_api_key),
):
    """Ask a question based on the knowledge base with SSE streaming."""
    session_id = request.session_id or "default"
    
    async def event_generator():
        try:
            async for event in qa_service.ask_stream(request.question, session_id=session_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
    qa_service.cache_manager.clear_session_cache(session_id)
    if cleared:
        return {"status": "success", "message": f"Session {session_id} cleared"}
    return {"status": "success", "message": f"Session {session_id} not found or already cleared"}

@router.post("/sync")
async def sync_knowledge_base(
    background_tasks: BackgroundTasks,
    config: Config = Depends(get_config),
    vector_store: VectorStoreAdapter = Depends(get_vector_store),
    bm25_store: BM25StoreAdapter = Depends(get_bm25_store),
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """Sync the vector database with Trilium Notes."""
    sync_service = SyncService(config, vector_store, bm25_store)
    background_tasks.add_task(sync_service.run_sync_job)
    return {"status": "success", "message": "知识库同步作业已在后台启动"}
