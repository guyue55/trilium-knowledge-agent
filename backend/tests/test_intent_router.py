# -*- coding: utf-8 -*-
"""意图路由器前置分类器单元测试."""

import pytest
from app.services.intent_router import IntentRouter


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def router():
    return IntentRouter()


def test_chitchat_greeting_intercept(router):
    """测试常规高频打招呼和问候的精确拦截."""
    assert router.classify("你好") == "CHITCHAT"
    assert router.classify("哈喽啊") == "CHITCHAT"
    assert router.classify("Good morning") == "CHITCHAT"
    assert router.classify("123456") == "CHITCHAT"


def test_chitchat_identity_intercept(router):
    """测试身份询问和谢词拦截."""
    assert router.classify("你是谁") == "CHITCHAT"
    assert router.classify("谢谢你") == "CHITCHAT"
    assert router.classify("Bye") == "CHITCHAT"


def test_technical_keyword_greetings_bypass(router):
    """测试包含核心技术/项目词的打招呼避开拦截，流向 RAG."""
    # 虽然匹配到 "你好"，但包含了技术词 "trilium" 或 "Docker"，不应当拦截！
    assert router.classify("你好 trilium") == "KNOWLEDGE_QUERY"
    assert router.classify("哈喽 Docker") == "KNOWLEDGE_QUERY"


def test_short_knowledge_nouns_bypass(router):
    """测试核心优化：2-3 字符的非技术多元化名词直接放行去 RAG."""
    # 原本字数小于等于 3 且非技术词的词会被一刀切拦截，重构后应完美放行！
    assert router.classify("考研") == "KNOWLEDGE_QUERY"
    assert router.classify("红烧肉") == "KNOWLEDGE_QUERY"
    assert router.classify("理财") == "KNOWLEDGE_QUERY"
    assert router.classify("烹饪") == "KNOWLEDGE_QUERY"
    assert router.classify("法学") == "KNOWLEDGE_QUERY"
    assert router.classify("相机") == "KNOWLEDGE_QUERY"


def test_empty_query_classification(router):
    """测试空输入判断."""
    assert router.classify("") == "CHITCHAT"
    assert router.classify(None) == "CHITCHAT"
