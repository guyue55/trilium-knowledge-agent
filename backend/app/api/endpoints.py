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
from app.api.schemas import AnswerResponse, QuestionRequest, DataTransformer
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

    # 运用 DataTransformer 提供健壮的接口格式转换，阻断运行时 Pydantic 校验报错并解耦底层数据结构
    config = get_config()
    raw_sources = result.get("sources", [])
    transformed_sources = [
        DataTransformer.to_source_document(src, trilium_base_url=config.trilium_base_url)
        for src in raw_sources
    ]

    return AnswerResponse(
        answer=result["answer"],
        sources=transformed_sources
    )

@router.post("/ask_stream")
async def ask_question_stream(
    request: QuestionRequest,
    qa_service: QAService = Depends(get_qa_service),
    _token: str = Depends(verify_api_key),
):
    """Ask a question based on the knowledge base with SSE streaming."""
    session_id = request.session_id or "default"
    
    async def event_generator():
        config = get_config()
        try:
            async for event in qa_service.ask_stream(request.question, session_id=session_id):
                # 运用 DataTransformer 统一对流式 sources 进行解耦转换，消除未来的字段缺失与类型不一致隐患
                if isinstance(event, dict) and event.get("type") == "sources" and "data" in event:
                    raw_sources = event["data"] or []
                    transformed_sources = [
                        DataTransformer.to_source_document(src, trilium_base_url=config.trilium_base_url).model_dump()
                        for src in raw_sources
                    ]
                    event = {"type": "sources", "data": transformed_sources}
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


@router.get("/memory")
async def get_agent_memory(_token: str = Depends(verify_api_key)) -> dict[str, Any]:
    """获取智能体的长期记忆 Markdown 内容，供前台可视化与审计."""
    logger.info("👉 [get_agent_memory] 端点被成功请求！")
    if not container.memory_manager:
        raise HTTPException(status_code=500, detail="MemoryManager 未初始化")
    content = await container.memory_manager.get_memory()
    return {"status": "success", "content": content}


@router.post("/memory")
async def update_agent_memory(
    payload: dict[str, Any],
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """手动保存/覆写长期记忆 Markdown 内容 (实现人机共治审计)."""
    if not container.memory_manager:
        raise HTTPException(status_code=500, detail="MemoryManager 未初始化")
    content = payload.get("content", "")
    success = await container.memory_manager.save_memory(content)
    if success:
        return {"status": "success", "message": "长期记忆物理落盘成功！"}
    raise HTTPException(status_code=500, detail="长期记忆写入失败")


import threading
import os

# 进程内重写互斥锁
_env_write_lock = threading.Lock()


def update_env_file(payload: dict[str, Any]):
    """更新 .env 配置文件，将页面修改落盘 (加物理排他锁与进程锁)."""
    with _env_write_lock:
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
            # 加共享锁读取
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    try:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    except (ImportError, AttributeError):
                        pass
                    lines = f.readlines()
            except Exception as e:
                logger.error(f"读取 .env 时加锁出错: {e}")
                # 兜底直接无锁读取
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
            "qwen_api_key": "QWEN_API_KEY",
            "use_reranker": "USE_RERANKER",
            "reranker_threshold": "RERANKER_THRESHOLD",
            "search_k": "SEARCH_K",
            "response_mode": "RESPONSE_MODE"
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
                    # 防御换行符注入漏洞，彻底剔除 \r 和 \n
                    updates[env_key] = str(val).replace("\r", "").replace("\n", "")
                    
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
                
        # 写入临时文件，再原子替换并强制同步刷盘，避免破坏原文件
        tmp_path = env_path.with_suffix(".env.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                try:
                    import fcntl
                    # 强加排他文件锁
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except (ImportError, AttributeError):
                    pass
                
                f.writelines(lines)
                f.flush()
                # 强制操作系统同步刷入闪存，保证掉电物理一致性
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            
            # POSIX 原子替换，安全落盘
            os.replace(tmp_path, env_path)
            logger.info("配置成功落盘持久化完成 (已应用物理锁与原子刷盘).")
        except Exception as e:
            logger.error(f"配置文件写盘并加物理锁时异常: {e}")
            # 兼容非标准环境下的普通写入
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)


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
    """获取所有会话列表及其标题和元信息."""
    try:
        sessions = await qa_service.session_manager.get_all_sessions_with_metadata()
    except AttributeError:
        sessions = await qa_service.session_manager.get_all_sessions()
    return {"status": "success", "sessions": sessions}


@router.get("/config")
async def get_config_api(
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """获取当前的非敏感配置参数，支持前端表单回显，并返回非致命预警信息."""
    config = container.config
    try:
        config.validate_complex_rules()
    except Exception as e:
        logger.warning(f"获取配置时的校验警告或非致命错误: {e}")
        
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
        "response_mode": config.response_mode,
        # 脱敏回显
        "openai_api_key": "******" if config.openai_api_key.strip() else "",
        "deepseek_api_key": "******" if config.deepseek_api_key.strip() else "",
        "gemini_api_key": "******" if config.gemini_api_key.strip() else "",
        "qwen_api_key": "******" if config.qwen_api_key.strip() else "",
        "warnings": getattr(config, "_warnings", [])
    }


@router.post("/config")
async def update_config_api(
    payload: dict[str, Any],
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """更新配置参数，原子校验，热重载内存中的大模型，并持久化落盘."""
    config = container.config
    
    # 1. 字典快照合并与清洗
    current_data = config.model_dump()
    update_data = {}
    
    if "llm_model_type" in payload:
        val = str(payload["llm_model_type"]).strip().lower()
        if val not in ["qwen", "openai", "ollama", "deepseek", "gemini"]:
            raise HTTPException(status_code=400, detail=f"不支持的大模型类型: {val}")
        update_data["llm_model_type"] = val
        
    if "llm_model_path" in payload:
        update_data["llm_model_path"] = str(payload["llm_model_path"]).strip()
        
    if "openai_api_base" in payload:
        update_data["openai_api_base"] = str(payload["openai_api_base"]).strip()
        
    if "openai_model_name" in payload:
        update_data["openai_model_name"] = str(payload["openai_model_name"]).strip()
        
    if "openai_api_key" in payload:
        key = str(payload["openai_api_key"]).strip()
        if key and not key.startswith("******"):
            update_data["openai_api_key"] = key
            
    if "deepseek_api_base" in payload:
        update_data["deepseek_api_base"] = str(payload["deepseek_api_base"]).strip()
        
    if "deepseek_model_name" in payload:
        update_data["deepseek_model_name"] = str(payload["deepseek_model_name"]).strip()
        
    if "deepseek_api_key" in payload:
        key = str(payload["deepseek_api_key"]).strip()
        if key and not key.startswith("******"):
            update_data["deepseek_api_key"] = key
            
    if "gemini_model_name" in payload:
        update_data["gemini_model_name"] = str(payload["gemini_model_name"]).strip()
        
    if "gemini_api_key" in payload:
        key = str(payload["gemini_api_key"]).strip()
        if key and not key.startswith("******"):
            update_data["gemini_api_key"] = key

    if "qwen_api_key" in payload:
        key = str(payload["qwen_api_key"]).strip()
        if key and not key.startswith("******"):
            update_data["qwen_api_key"] = key

    if "trilium_base_url" in payload:
        update_data["trilium_base_url"] = str(payload["trilium_base_url"]).strip()
            
    if "use_reranker" in payload:
        update_data["use_reranker"] = bool(payload["use_reranker"])
        
    if "reranker_threshold" in payload:
        try:
            val = float(payload["reranker_threshold"])
            if not (0.0 <= val <= 1.0):
                raise ValueError()
            update_data["reranker_threshold"] = val
        except Exception:
            raise HTTPException(status_code=400, detail="reranker_threshold 必须是 0.0 ~ 1.0 之间的浮点数")
        
    if "search_k" in payload:
        try:
            val = int(payload["search_k"])
            if not (1 <= val <= 20):
                raise ValueError()
            update_data["search_k"] = val
        except Exception:
            raise HTTPException(status_code=400, detail="search_k 必须是 1 ~ 20 之间的整数")

    if "response_mode" in payload:
        val = str(payload["response_mode"]).strip().lower()
        if val not in ["strict", "balanced", "creative"]:
            raise HTTPException(status_code=400, detail=f"不支持的回答模式: {val}")
        update_data["response_mode"] = val

    # 2. 构造临时对象并进行全量校验 (Copy-on-Validate)
    merged_data = {**current_data, **update_data}
    try:
        temp_config = Config(**merged_data)
        temp_config.validate_complex_rules()
    except Exception as e:
        logger.warning(f"原子校验失败，不污染全局配置单例: {e}")
        raise HTTPException(status_code=400, detail=f"新配置校验未通过: {str(e)}")

    # 3. 校验全部通过后，原子更新到全局单例
    config.__dict__.update(temp_config.__dict__)
    config._warnings = getattr(temp_config, "_warnings", [])

    # 4. 动态热重载 LLM Adapter (Offload 驱动构建，消除主线程同步网络与 CPU 阻塞)
    try:
        import asyncio
        from app.llm.factory import LLMFactory
        new_adapter = await asyncio.to_thread(LLMFactory.create_llm, config)
        container.llm_adapter = new_adapter
        logger.info("配置修改成功，全局 LLM 适配器驱动已内存热重装！")
    except Exception as e:
        logger.error(f"热重载 LLM 适配器驱动异常: {e}")
        raise HTTPException(status_code=500, detail=f"大模型重载重连失败: {str(e)}")

    # 5. 同步落盘
    try:
        await asyncio.to_thread(update_env_file, payload)
    except Exception as e:
        logger.warning(f"配置落盘失败: {e}")
        
    return {
        "status": "success",
        "message": "配置更新成功，服务已被实时动态重载！",
        "warnings": getattr(config, "_warnings", [])
    }


@router.get("/config/detect_ollama")
async def detect_ollama_models(
    config: Config = Depends(get_config),
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """探测本地运行的 Ollama 服务并自动拉取已下载的模型列表."""
    api_base = config.openai_api_base or "http://localhost:11434"
    base = api_base.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    url = f"{base}/api/tags"
    
    import requests
    try:
        # 极速探测 1 秒
        response = await asyncio.to_thread(requests.get, url, timeout=1.0)
        if response.status_code == 200:
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return {"status": "success", "models": models}
        return {"status": "success", "models": []}
    except Exception as e:
        logger.warning(f"Ollama 本地探测失败 (地址: {url}): {e}")
        return {"status": "success", "models": []}


@router.post("/config/test_connection")
async def test_connection_api(
    payload: dict[str, Any],
    _token: str = Depends(verify_api_key)
) -> dict[str, Any]:
    """测试指定服务连接配置的可达性 (Trilium, Ollama, API Key 等)."""
    target = payload.get("target", "")
    import requests
    
    if target == "trilium":
        url = payload.get("trilium_base_url", "").strip()
        if not url:
            return {"status": "error", "message": "Trilium 服务地址不能为空"}
        try:
            # 探测 Trilium 首部页面连通性
            response = await asyncio.to_thread(requests.get, url, timeout=1.5)
            return {"status": "success", "connected": True, "message": f"Trilium 连通正常 (HTTP {response.status_code})"}
        except Exception as e:
            return {"status": "error", "connected": False, "message": f"连接失败: {str(e)}"}
            
    elif target == "llm":
        provider = payload.get("llm_model_type", "").strip().lower()
        if provider == "ollama":
            api_base = payload.get("openai_api_base", "").strip() or "http://localhost:11434"
            base = api_base.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3].rstrip("/")
            url = f"{base}/api/tags"
            try:
                response = await asyncio.to_thread(requests.get, url, timeout=1.5)
                if response.status_code == 200:
                    return {"status": "success", "connected": True, "message": "Ollama 本地服务在线，连通正常！"}
                return {"status": "error", "connected": False, "message": f"Ollama 返回异常状态码: {response.status_code}"}
            except Exception as e:
                return {"status": "error", "connected": False, "message": f"无法连通 Ollama 服务: {str(e)}"}
                
        elif provider in ["openai", "deepseek", "gemini"]:
            api_base = payload.get("openai_api_base", "").strip()
            if provider == "deepseek":
                api_base = payload.get("deepseek_api_base", "").strip() or "https://api.deepseek.com/v1"
            elif provider == "gemini":
                api_base = "https://generativelanguage.googleapis.com"
            elif not api_base:
                api_base = "https://api.openai.com/v1"
                
            try:
                # 仅物理网关连通探测
                response = await asyncio.to_thread(requests.head, api_base, timeout=1.5)
                return {"status": "success", "connected": True, "message": f"{provider.upper()} API 网关可达"}
            except Exception as e:
                return {"status": "error", "connected": False, "message": f"连接 API 网关超时或失败: {str(e)}"}
                
    return {"status": "error", "message": f"未知的测试目标: {target}"}

