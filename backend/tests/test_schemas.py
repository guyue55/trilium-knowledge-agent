# -*- coding: utf-8 -*-
"""API Schemas模块的测试用例.

测试Pydantic模型的验证逻辑。
"""

import pytest
from pydantic import ValidationError

from app.api.schemas import AnswerResponse, ErrorDetail, QuestionRequest, SourceDocument


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
        err_msg = str(exc_info.value).lower()
        assert "不能为空" in err_msg or "at least 1" in err_msg or "too_short" in err_msg

    def test_whitespace_only_question_raises_error(self):
        """测试只包含空白的问题抛出验证错误."""
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question="   ")
        err_msg = str(exc_info.value).lower()
        assert "不能为空" in err_msg or "at least 1" in err_msg or "too_short" in err_msg

    def test_too_long_question_raises_error(self):
        """测试超长问题抛出验证错误."""
        long_question = "测" * 1001  # 超过1000字符
        with pytest.raises(ValidationError) as exc_info:
            QuestionRequest(question=long_question)
        err_msg = str(exc_info.value).lower()
        assert "字符" in err_msg or "length" in err_msg or "too_long" in err_msg or "at most" in err_msg

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
            url="http://localhost:8080/#?noteId=abc123",
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
            SourceDocument(source="trilium:test", content=long_content)

    def test_title_max_length(self):
        """测试标题最大长度限制."""
        long_title = "测" * 201  # 超过200字符
        with pytest.raises(ValidationError):
            SourceDocument(source="trilium:test", title=long_title)


class TestErrorDetail:
    """测试ErrorDetail模型."""

    def test_valid_error_detail(self):
        """测试有效错误详情."""
        error = ErrorDetail(
            code="VECTOR_DB_ERROR",
            message="向量数据库查询失败",
            details="Connection timeout after 10s",
        )
        assert error.code == "VECTOR_DB_ERROR"
        assert error.message == "向量数据库查询失败"
        assert error.details == "Connection timeout after 10s"

    def test_error_detail_without_details(self):
        """测试不包含详细信息的错误."""
        error = ErrorDetail(code="INVALID_INPUT", message="输入参数无效")
        assert error.code == "INVALID_INPUT"
        assert error.message == "输入参数无效"
        assert error.details is None


class TestAnswerResponse:
    """测试AnswerResponse模型."""

    def test_valid_answer_response(self):
        """测试有效答案响应."""
        response = AnswerResponse(
            answer="这是答案内容",
            sources=[SourceDocument(source="trilium:abc123", title="源文档标题")],
        )
        assert response.answer == "这是答案内容"
        assert len(response.sources) == 1
        assert response.sources[0].source == "trilium:abc123"
        assert response.error is None

    def test_answer_response_with_error(self):
        """测试包含错误信息的答案响应."""
        error = ErrorDetail(code="LLM_ERROR", message="语言模型生成失败")
        response = AnswerResponse(answer="抱歉，无法生成答案", error=error)
        assert response.answer == "抱歉，无法生成答案"
        assert response.error.code == "LLM_ERROR"
        assert response.sources is None

    def test_answer_response_without_sources(self):
        """测试不包含源文档的答案响应."""
        response = AnswerResponse(answer="简单回答")
        assert response.answer == "简单回答"
        assert response.sources is None
        assert response.error is None


class TestDataTransformer:
    """测试 DataTransformer 接口适配层与转换逻辑."""

    def test_transformer_with_complete_fields(self):
        """测试在源字段完整时，自动高保真地转换."""
        from app.api.schemas import DataTransformer
        
        raw_src = {
            "source": "trilium:abc123",
            "note_id": "abc123",
            "title": "测试知识库笔记",
            "content": "这是一大段很长的正文切片内容，测试截断。",
            "url": "http://my-trilium.com/#root/abc123"
        }
        
        doc = DataTransformer.to_source_document(raw_src, trilium_base_url="http://localhost:8080")
        assert doc.source == "trilium:abc123"
        assert doc.title == "测试知识库笔记"
        assert doc.content == "这是一大段很长的正文切片内容，测试截断。"
        assert doc.url == "http://my-trilium.com/#root/abc123"

    def test_transformer_protects_missing_source_and_url_generation(self):
        """测试在缺少 source 和 url 时，自适应降级并拼装生成完美的直连链接."""
        from app.api.schemas import DataTransformer
        
        # 缺少 source 且缺少 url，但具有 note_id
        raw_src = {
            "note_id": "xyz789",
            "title": "未知名",
            "content": "一些正文..."
        }
        
        doc = DataTransformer.to_source_document(raw_src, trilium_base_url="http://localhost:8080/")
        # 1. 自动推导 source 为 trilium:xyz789
        assert doc.source == "trilium:xyz789"
        # 2. 自动拼装正确的 URL 链接
        assert doc.url == "http://localhost:8080/#root/xyz789"
        assert doc.title == "未知名"

    def test_transformer_safe_truncation(self):
        """测试超长内容在 DTO 转换阶段被安全物理截断，减少传输开销."""
        from app.api.schemas import DataTransformer
        
        long_text = "我" * 600
        raw_src = {
            "note_id": "truncated_note",
            "content": long_text
        }
        
        doc = DataTransformer.to_source_document(raw_src, trilium_base_url="http://localhost:8080")
        assert len(doc.content) == 500
        assert doc.content == "我" * 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
