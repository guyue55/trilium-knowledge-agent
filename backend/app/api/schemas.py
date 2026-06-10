# -*- coding: utf-8 -*-
"""用于 API 请求/响应验证的 Pydantic 模型以及高层 DTO 数据适配器."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, ConfigDict


class QuestionRequest(BaseModel):
    """用于提问的请求模型.

    包含输入验证，确保问题格式正确且长度合理。
    """
    model_config = ConfigDict(
        json_schema_extra={"example": {"question": "Trilium Notes 如何创建代码笔记？"}}
    )

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="用户提出的问题，长度在1-1000字符之间",
    )
    session_id: str | None = Field(
        default="default",
        max_length=100,
        description="会话ID，用于区分不同用户的对话历史",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """验证问题内容并清洗空白，拦截潜在 XSS 入侵."""
        v = v.strip()

        # 检查是否为空
        if not v:
            raise ValueError("问题不能为空或只包含空白字符")

        # 检查是否包含恶意内容（基础检测）
        malicious_patterns = ["<script", "javascript:", "onerror="]
        for pattern in malicious_patterns:
            if pattern.lower() in v.lower():
                raise ValueError(f"问题包含潜在的恶意内容: {pattern}")

        return v


class SourceDocument(BaseModel):
    """源文档模型.

    表示问答系统返回的文档来源信息。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "trilium:abc123",
                "title": "Trilium使用指南",
                "content": "这是一篇关于Trilium使用的指南...",
                "url": "http://localhost:8080/#?noteId=abc123",
            }
        }
    )

    source: str = Field(..., description="文档来源标识")
    content: str | None = Field(None, max_length=500, description="文档内容预览（最多500字符）")
    title: str | None = Field(None, max_length=200, description="文档标题（最多200字符）")
    url: str | None = Field(None, description="文档URL链接")


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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "在Trilium中创建代码笔记非常简单...",
                "sources": [
                    {
                        "source": "trilium:abc123",
                        "title": "代码笔记教程",
                        "content": "代码笔记可以...",
                        "url": "http://localhost:8080/#?noteId=abc123",
                    }
                ],
                "error": None,
            }
        }
    )

    answer: str = Field(..., description="生成的答案")
    sources: list[SourceDocument] | None = Field(default=None, description="源文档列表")
    error: ErrorDetail | None = Field(default=None, description="错误信息（如果有）")


class DataTransformer:
    """高阶接口适配与协议转换器.

    实现业务模型/数据存储层到前端 API DTO 的原子解耦转换，从而完美支持外部库、
    数据库以及切片数据字段的任意后续演进变更。
    """

    @staticmethod
    def to_source_document(raw_source: dict, trilium_base_url: str = "") -> SourceDocument:
        """自适应转换器：将任意字典源转化为具有严格 Pydantic V2 规约的高可靠 SourceDocument DTO.

        支持 note_id、source 自动互转并自适应生成完美的直连物理链接，同时对大文本自动截断
        以节省 API 同步传输带宽负担。
        """
        note_id = raw_source.get("note_id") or ""
        
        # 1. source 属性防崩溃自适应：如果缺少必填的 source，通过 trilium:{note_id} 动态推导或安全降级
        source_id = raw_source.get("source") or (f"trilium:{note_id}" if note_id else "unknown")
        
        # 2. 链接完美拼装适配：若无外部现成 URL 链接，直接依据 base_url 和 note_id 自适应构建
        url = raw_source.get("url")
        if not url and note_id and trilium_base_url:
            clean_base = trilium_base_url.rstrip("/")
            url = f"{clean_base}/#root/{note_id}"

        # 3. 500字安全物理截断保护，防止大文档切片撑爆前端 DOM 树
        raw_content = raw_source.get("content") or ""
        content_preview = raw_content[:500] if raw_content else None

        return SourceDocument(
            source=source_id,
            content=content_preview,
            title=raw_source.get("title") or "未知文档",
            url=url
        )
