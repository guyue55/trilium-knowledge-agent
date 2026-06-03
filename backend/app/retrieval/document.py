# -*- coding: utf-8 -*-
"""基础文档类型."""

from typing import Dict, Any

class Document:
    def __init__(self, page_content: str, metadata: Dict[str, Any] = None):
        self.page_content = page_content
        self.metadata = metadata or {}
