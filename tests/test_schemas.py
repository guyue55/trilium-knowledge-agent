# -*- coding: utf-8 -*-
"""API Schemas模块的测试用例.

测试Pydantic模型的验证逻辑。
"""

import pytest
from pydantic import ValidationError
from app.api.schemas import QuestionRequest, SourceDocument, AnswerResponse, ErrorDetail


class TestQuestionRequest:
    """测试QuestionRequest模型."""
    
    def test_valid_question(self):
        """测试有效问题."""
        request = QuestionRequest(question="Trilium如何创建笔记？")
        assert request.question == "Trilium如何创建笔记？"
        
    def test_question_strips_whitespace(self):
        """测试问题去除首尾空白."""
        request = QuestionRequest(question="  测试问题  ")
        assert request.question == "测试问题"
        
    def test_empty_question_raises_error(self):
        """测试空问题抛出验证错误."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="")
        assert "问题不能为空" in str(exc_info.value)
        
    def test_whitespace_only_question_raises_error(self):
        """测试只包含空白的问题抛出验证错误."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="   ")
        assert "问题不能为空" in str(exc_info.value)
        
    def test_too_long_question_raises_error(self):
        """测试超长问题抛出验证错误."""
        long_question = "测" * 1001  # 超过1000字符
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question=long_question)
        assert "字符" in str(exc_info.value).lower() or "length" in str(exc_info.value).lower()
        
    def test_malicious_script_tag_raises_error(self):
        """测试包含script标签的问题抛出验证错误."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="这是一个问题<script>alert('xss')</script>")
        assert "恶意内容" in str(exc_info.value)
        
    def test_malicious_javascript_raises_error(self):
        """测试包含javascript的问题抛出验证错误."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="javascript:alert('xss')")
        assert "恶意内容" in str(exc_info.value)
        
    def test_malicious_onerror_raises_error(self):
        """测试包含onerror的问题抛出验证错误."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="<img src=x onerror=alert('xss')>")
        assert "恶意内容" in str(exc_info.value)


class TestSourceDocument:
    """测试SourceDocument模型."""
    
    def test_valid_source_document(self):
        """测试有效源文档."""
        doc = SourceDocument(
            source="trilium:abc123",
            title="测试标题",
            content="测试内容",
            url="http://localhost:8080/#?noteId=abc123"
        )
        assert doc.source == "trilium:abc123"
        assert doc.title == "测试标题"
        assert doc.content == "测试内容"
        assert doc.url == "http://localhost:8080/#?noteId=abc123"
        
    def test_source_document_with_optional_fields(self):
        """测试只包含必填字段的源文档."""
        doc = SourceDocument(source="trilium:xyz789")
        assert doc.source == "trilium:xyz789"
        assert doc.title is None
        assert doc.content is None
        assert doc.url is None
        
    def test_content_max_length(self):
        """测试内容最大长度限制."""
        long_content = "测" * 501  # 超过500字符
        with pytest.raises(ValidationError):
            SourceDocument(
                source="trilium:test",
                content=long_content
            )
            
    def test_title_max_length(self):
        """测试标题最大长度限制."""
        long_title = "测" * 201  # 超过200字符
        with pytest.raises(ValidationError):
            SourceDocument(
                source="trilium:test",
                title=long_title
            )


class TestErrorDetail:
    """测试ErrorDetail模型."""
    
    def test_valid_error_detail(self):
        """测试有效错误详情."""
        error = ErrorDetail(
            code="VECTOR_DB_ERROR",
            message="向量数据库查询失败",
            details="Connection timeout after 10s"
        )
        assert error.code == "VECTOR_DB_ERROR"
        assert error.message == "向量数据库查询失败"
        assert error.details == "Connection timeout after 10s"
        
    def test_error_detail_without_details(self):
        """测试不包含详细信息的错误."""
        error = ErrorDetail(
            code="INVALID_INPUT",
            message="输入参数无效"
        )
        assert error.code == "INVALID_INPUT"
        assert error.message == "输入参数无效"
        assert error.details is None


class TestAnswerResponse:
    """测试AnswerResponse模型."""
    
    def test_valid_answer_response(self):
        """测试有效答案响应."""
        response = AnswerResponse(
            answer="这是答案内容",
            sources=[
                SourceDocument(
                    source="trilium:abc123",
                    title="源文档标题"
                )
            ]
        )
        assert response.answer == "这是答案内容"
        assert len(response.sources) == 1
        assert response.sources[0].source == "trilium:abc123"
        assert response.error is None
        
    def test_answer_response_with_error(self):
        """测试包含错误信息的答案响应."""
        error = ErrorDetail(
            code="LLM_ERROR",
            message="语言模型生成失败"
        )
        response = AnswerResponse(
            answer="抱歉，无法生成答案",
            error=error
        )
        assert response.answer == "抱歉，无法生成答案"
        assert response.error.code == "LLM_ERROR"
        assert response.sources is None
        
    def test_answer_response_without_sources(self):
        """测试不包含源文档的答案响应."""
        response = AnswerResponse(answer="简单回答")
        assert response.answer == "简单回答"
        assert response.sources is None
        assert response.error is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
