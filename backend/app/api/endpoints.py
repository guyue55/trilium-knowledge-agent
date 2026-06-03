# -*- coding: utf-8 -*-
"""API endpoints for the Trilium Knowledge Agent."""

from __future__ import annotations

from typing import Any
import json
from pathlib import Path
from loguru import logger
from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_qa_service, get_config, get_vector_store
from app.api.schemas import AnswerResponse, QuestionRequest
from app.core.config import Config
from app.core.container import container
from app.core.security import verify_api_key
from app.retrieval.vector_store import VectorStoreAdapter
from app.services.qa_service import QAService
from app.services.sync_service import SyncService

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
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """Sync the vector database with Trilium Notes."""
    sync_service = SyncService(config, vector_store)
    background_tasks.add_task(sync_service.run_sync_job)
    return {"status": "success", "message": "知识库同步作业已在后台启动"}


def update_env_file(payload: dict[str, Any]):
    """更新 .env 配置文件，将页面修改落盘."""
    from app.core.config import PROJECT_ROOT
    paths_to_try = [
        Path(".env"),
        Path("backend/.env"),
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "backend" / ".env"
    ]
    env_path = None
    for p in paths_to_try:
        if p.exists() and p.is_file():
            env_path = p
            break
            
    if not env_path:
        if (PROJECT_ROOT / "backend").exists():
            env_path = PROJECT_ROOT / "backend" / ".env"
        else:
            env_path = PROJECT_ROOT / ".env"
            
    logger.info(f"落盘配置路径选择: {env_path}")
    
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    env_keys_to_update = {
        "trilium_base_url": "TRILIUM_BASE_URL",
        "llm_model_type": "LLM_MODEL_TYPE",
        "llm_model_path": "LLM_MODEL_PATH",
        "openai_api_base": "OPENAI_API_BASE",
        "openai_model_name": "OPENAI_MODEL_NAME",
        "openai_api_key": "OPENAI_API_KEY",
        "deepseek_api_base": "DEEPSEEK_API_BASE",
        "deepseek_model_name": "DEEPSEEK_MODEL_NAME",
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "gemini_model_name": "GEMINI_MODEL_NAME",
        "gemini_api_key": "GEMINI_API_KEY",
        "use_reranker": "USE_RERANKER",
        "reranker_threshold": "RERANKER_THRESHOLD",
        "search_k": "SEARCH_K"
    }
    
    updates = {}
    for py_key, env_key in env_keys_to_update.items():
        if py_key in payload:
            val = payload[py_key]
            if py_key.endswith("key") and str(val).startswith("******"):
                continue
            if isinstance(val, bool):
                updates[env_key] = "true" if val else "false"
            else:
                updates[env_key] = str(val)
                
    updated_keys = set()
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("#") or "=" not in line_strip:
            continue
        parts = line_strip.split("=", 1)
        key = parts[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}\n"
            updated_keys.add(key)
            
    for key, val in updates.items():
        if key not in updated_keys:
            lines.append(f"{key}={val}\n")
            
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    logger.info("配置成功落盘持久化完成。")


@router.get("/session/{session_id}")
async def get_session_history(
    session_id: str,
    qa_service: QAService = Depends(get_qa_service),
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """获取指定会话的完整历史聊天记录，供前端点击无缝回显加载."""
    history = await qa_service.session_manager.get_history(session_id)
    return {
        "status": "success",
        "history": [{"role": msg.role, "content": msg.content} for msg in history]
    }


@router.get("/sessions")
async def get_sessions(
    qa_service: QAService = Depends(get_qa_service),
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """获取所有会话列表及其标题."""
    sessions = await qa_service.session_manager.get_all_sessions()
    return {"status": "success", "sessions": sessions}


@router.get("/config")
async def get_config_api(
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """获取当前的非敏感配置参数，支持前端表单回显."""
    config = container.config
    return {
        "llm_model_type": config.llm_model_type,
        "llm_model_path": config.llm_model_path,
        "openai_api_base": config.openai_api_base,
        "openai_model_name": config.openai_model_name,
        "deepseek_api_base": config.deepseek_api_base,
        "deepseek_model_name": config.deepseek_model_name,
        "gemini_model_name": config.gemini_model_name,
        "trilium_base_url": config.trilium_base_url,
        "use_reranker": config.use_reranker,
        "reranker_threshold": config.reranker_threshold,
        "search_k": config.search_k,
        # 脱敏回显
        "openai_api_key": "******" if config.openai_api_key.strip() else "",
        "deepseek_api_key": "******" if config.deepseek_api_key.strip() else "",
        "gemini_api_key": "******" if config.gemini_api_key.strip() else ""
    }


@router.post("/config")
async def update_config_api(
    payload: dict[str, Any],
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """更新配置参数，热重载内存中的大模型，并持久化落盘."""
    config = container.config
    
    if "llm_model_type" in payload:
        val = str(payload["llm_model_type"]).strip().lower()
        if val not in ["gpt4all", "qwen", "openai", "ollama", "deepseek", "gemini"]:
            raise HTTPException(status_code=400, detail=f"不支持的大模型类型: {val}")
        config.llm_model_type = val
        
    if "llm_model_path" in payload:
        config.llm_model_path = str(payload["llm_model_path"]).strip()
        
    if "openai_api_base" in payload:
        config.openai_api_base = str(payload["openai_api_base"]).strip()
        
    if "openai_model_name" in payload:
        config.openai_model_name = str(payload["openai_model_name"]).strip()
        
    if "openai_api_key" in payload:
        key = str(payload["openai_api_key"]).strip()
        if key and not key.startswith("******"):
            config.openai_api_key = key
            
    if "deepseek_api_base" in payload:
        config.deepseek_api_base = str(payload["deepseek_api_base"]).strip()
        
    if "deepseek_model_name" in payload:
        config.deepseek_model_name = str(payload["deepseek_model_name"]).strip()
        
    if "deepseek_api_key" in payload:
        key = str(payload["deepseek_api_key"]).strip()
        if key and not key.startswith("******"):
            config.deepseek_api_key = key
            
    if "gemini_model_name" in payload:
        config.gemini_model_name = str(payload["gemini_model_name"]).strip()
        
    if "gemini_api_key" in payload:
        key = str(payload["gemini_api_key"]).strip()
        if key and not key.startswith("******"):
            config.gemini_api_key = key

    if "trilium_base_url" in payload:
        config.trilium_base_url = str(payload["trilium_base_url"]).strip()
            
    if "use_reranker" in payload:
        config.use_reranker = bool(payload["use_reranker"])
        
    if "reranker_threshold" in payload:
        try:
            val = float(payload["reranker_threshold"])
            if not (0.0 <= val <= 1.0):
                raise ValueError()
            config.reranker_threshold = val
        except Exception:
            raise HTTPException(status_code=400, detail="reranker_threshold 必须是 0.0 ~ 1.0 之间的浮点数")
        
    if "search_k" in payload:
        try:
            val = int(payload["search_k"])
            if not (1 <= val <= 20):
                raise ValueError()
            config.search_k = val
        except Exception:
            raise HTTPException(status_code=400, detail="search_k 必须是 1 ~ 20 之间的整数")

    # 验证新配置
    try:
        config.validate_complex_rules()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"新配置校验未通过: {str(e)}")

    # 动态热重载 LLM Adapter
    try:
        from app.llm.factory import LLMFactory
        new_adapter = LLMFactory.create_llm(config)
        container.llm_adapter = new_adapter
        logger.info("配置修改成功，全局 LLM 适配器驱动已内存热重装！")
    except Exception as e:
        logger.error(f"热重载 LLM 适配器驱动异常: {e}")
        raise HTTPException(status_code=500, detail=f"大模型重载重连失败: {str(e)}")

    # 同步落盘
    try:
        update_env_file(payload)
    except Exception as e:
        logger.warning(f"配置落盘失败: {e}")
        
    return {"status": "success", "message": "配置更新成功，服务已被实时动态重载！"}

