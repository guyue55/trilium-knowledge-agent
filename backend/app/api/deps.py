# -*- coding: utf-8 -*-
"""FastAPI 依赖注入模块.

为路由层提供解耦的组件依赖。
"""

from fastapi import Request, HTTPException, status
from loguru import logger

from app.core.config import Config
from app.core.container import container
from app.llm.base import LLMAdapter
from app.retrieval.vector_store import VectorStoreAdapter
from app.services.qa_service import QAService
from app.services.retrieval_service import RetrievalService


def get_config() -> Config:
    return container.config


def get_llm_adapter() -> LLMAdapter:
    if not container.llm_adapter:
        logger.error("LLM Adapter 尚未初始化")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="LLM Service Unavailable"
        )
    return container.llm_adapter


def get_vector_store() -> VectorStoreAdapter:
    if not container.vector_store:
        logger.error("Vector Store 尚未初始化")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Vector Store Service Unavailable"
        )
    return container.vector_store


def get_retrieval_service() -> RetrievalService:
    if not container.vector_store or not container.reranker:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Retrieval dependencies are not fully initialized"
        )
    return RetrievalService(
        config=container.config,
        vector_store=container.vector_store,
        reranker=container.reranker
    )


def get_qa_service() -> QAService:
    if not container.cache_manager or not container.session_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="QA dependencies are not fully initialized"
        )
    
    retrieval_service = get_retrieval_service()
    llm_adapter = get_llm_adapter()
    
    return QAService(
        llm_adapter=llm_adapter,
        retrieval_service=retrieval_service,
        cache_manager=container.cache_manager,
        session_manager=container.session_manager
    )
