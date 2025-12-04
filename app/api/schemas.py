# -*- coding: utf-8 -*-
"""用于API请求/响应验证的Pydantic模型."""

from pydantic import BaseModel
from typing import List, Optional


class QuestionRequest(BaseModel):
    """用于提问的请求模型."""
    question: str


class SourceDocument(BaseModel):
    """源文档模型."""
    source: str
    content: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None


class AnswerResponse(BaseModel):
    """回答问题的响应模型."""
    answer: str
    sources: Optional[List[SourceDocument]] = None