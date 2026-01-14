# -*- coding: utf-8 -*-
"""异常处理模块的单元测试."""

import pytest
from fastapi import HTTPException, status
from app.core.exceptions import (
    BaseAppException,
    ConfigException,
    KnowledgeBaseException,
    LLMException,
    TriliumException,
    QAException,
    handle_app_exception
)


class TestExceptions:
    """异常类的测试用例."""
    
    def test_base_app_exception(self):
        """测试基础异常类."""
        exc = BaseAppException("测试错误", error_code="TEST001")
        
        assert exc.message == "测试错误"
        assert exc.error_code == "TEST001"
        assert "BaseAppException" in str(exc)
        assert "测试错误" in str(exc)
        
    def test_config_exception(self):
        """测试配置异常."""
        exc = ConfigException("配置错误", error_code="CFG001")
        
        assert isinstance(exc, BaseAppException)
        assert exc.message == "配置错误"
        assert exc.error_code == "CFG001"
        
    def test_knowledge_base_exception(self):
        """测试知识库异常."""
        exc = KnowledgeBaseException("知识库错误")
        
        assert isinstance(exc, BaseAppException)
        assert exc.message == "知识库错误"
        
    def test_llm_exception(self):
        """测试LLM异常."""
        exc = LLMException("模型加载失败")
        
        assert isinstance(exc, BaseAppException)
        assert exc.message == "模型加载失败"
        
    def test_trilium_exception(self):
        """测试Trilium异常."""
        exc = TriliumException("连接失败")
        
        assert isinstance(exc, BaseAppException)
        assert exc.message == "连接失败"
        
    def test_qa_exception(self):
        """测试问答服务异常."""
        exc = QAException("问答失败")
        
        assert isinstance(exc, BaseAppException)
        assert exc.message == "问答失败"


class TestHandleAppException:
    """异常处理函数的测试用例."""
    
    def test_handle_config_exception(self):
        """测试处理配置异常."""
        exc = ConfigException("配置错误", error_code="CFG001")
        http_exc = handle_app_exception(exc, "config_error")
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exc.detail["error"] == "config_error"
        assert http_exc.detail["message"] == "配置错误"
        assert http_exc.detail["error_code"] == "CFG001"
        
    def test_handle_qa_exception(self):
        """测试处理QA异常."""
        exc = QAException("问答失败")
        http_exc = handle_app_exception(exc)
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == status.HTTP_400_BAD_REQUEST
        
    def test_handle_trilium_exception(self):
        """测试处理Trilium异常."""
        exc = TriliumException("连接失败")
        http_exc = handle_app_exception(exc)
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == status.HTTP_502_BAD_GATEWAY
        
    def test_handle_llm_exception(self):
        """测试处理LLM异常."""
        exc = LLMException("模型加载失败")
        http_exc = handle_app_exception(exc)
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == status.HTTP_502_BAD_GATEWAY
        
    def test_handle_generic_exception(self):
        """测试处理通用异常."""
        exc = BaseAppException("通用错误")
        http_exc = handle_app_exception(exc)
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
