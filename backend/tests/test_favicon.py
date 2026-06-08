# -*- coding: utf-8 -*-
"""Favicon 浏览器图标与主页路由的集成测试用例."""

from fastapi.testclient import TestClient
from app.main import app


def test_favicon_endpoint():
    """测试 /favicon.ico 路由能够正常拦截并返回 SVG 图标，杜绝 404."""
    client = TestClient(app)
    response = client.get("/favicon.ico")
    
    # 状态码应当为 200 (成功响应) 或 204 (软退化静默响应)
    assert response.status_code in [200, 204]
    
    if response.status_code == 200:
        assert "image/svg+xml" in response.headers["content-type"]


def test_root_endpoint_contains_favicon_tag():
    """测试主路由返回的 HTML 中已正确包含 favicon 矢量标签声明."""
    client = TestClient(app)
    response = client.get("/")
    
    # 状态码应当为 200
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    # HTML 内容中应当包含 favicon.svg 引用
    assert "favicon.svg" in response.text
    assert 'link rel="icon"' in response.text
