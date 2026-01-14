# -*- coding: utf-8 -*-
"""用于API请求/响应验证的Pydantic模型."""

from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import Optional


class QuestionRequest(BaseModel):
    """用于提问的请求模型.
    
    包含输入验证，确保问题格式正确且长度合理。
    """
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="用户提出的问题，长度在1-1000字符之间"
    )
    session_id: str | None = Field(
        default="default",
        max_length=100,
        description="会话ID，用于区分不同用户的对话历史"
    )
    
    @validator('question')
    def validate_question(cls, v: str) -> str:
        """验证问题内容.
        
        Args:
            v: 问题字符串.
            
        Returns:
            str: 清理后的问题字符串.
            
        Raises:
            ValueError: 当问题内容不合法时.
        """
        # 去除首尾空白
        v = v.strip()
        
        # 检查是否为空
        if not v:
            raise ValueError("问题不能为空或只包含空白字符")
        
        # 检查是否包含恶意内容（基础检测）
        malicious_patterns = ['<script', 'javascript:', 'onerror=']
        for pattern in malicious_patterns:
            if pattern.lower() in v.lower():
                raise ValueError(f"问题包含潜在的恶意内容: {pattern}")
        
        return v
    
    class Config:
        """Pydantic配置."""
        schema_extra = {
            "example": {
                "question": "Trilium Notes 如何创建代码笔记？"
            }
        }


class SourceDocument(BaseModel):
    """源文档模型.
    
    表示问答系统返回的文档来源信息。
    """
    source: str = Field(..., description="文档来源标识")
    content: str | None = Field(None, max_length=500, description="文档内容预览（最多500字符）")
    title: str | None = Field(None, max_length=200, description="文档标题（最多200字符）")
    url: str | None = Field(None, description="文档URL链接")
    
    class Config:
        """Pydantic配置."""
        schema_extra = {
            "example": {
                "source": "trilium:abc123",
                "title": "Trilium使用指南",
                "content": "这是一篇关于Trilium使用的指南...",
                "url": "http://localhost:8080/#?noteId=abc123"
            }
        }


class ErrorDetail(BaseModel):
    """错误详情模型.
    
    提供标准化的错误信息格式。
    """
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: str | None = Field(None, description="详细错误信息（调试模式）")


class AnswerResponse(BaseModel):
    """回答问题的响应模型.
    
    包含答案、来源文档以及可能的错误信息。
    """
    answer: str = Field(..., description="生成的答案")
    sources: list[SourceDocument] | None = Field(default=None, description="源文档列表")
    error: ErrorDetail | None = Field(default=None, description="错误信息（如果有）")
    
    class Config:
        """Pydantic配置."""
        schema_extra = {
            "example": {
                "answer": "在Trilium中创建代码笔记非常简单...",
                "sources": [
                    {
                        "source": "trilium:abc123",
                        "title": "代码笔记教程",
                        "content": "代码笔记可以...",
                        "url": "http://localhost:8080/#?noteId=abc123"
                    }
                ],
                "error": None
            }
        }
