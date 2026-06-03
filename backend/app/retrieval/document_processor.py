# -*- coding: utf-8 -*-
"""文档处理与树形层级切分."""

import re
from typing import List, Dict, Any

from loguru import logger
from app.core.config import Config
from app.retrieval.document import Document


class DocumentProcessor:
    """负责将 Trilium 原始笔记进行高精度树层级感知切块 (Hierarchical Chunking) 的文档处理器."""

    def __init__(self, config: Config):
        self.config = config
        self.chunk_size = config.chunk_size
        self.chunk_overlap = config.chunk_overlap

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """将一组完整的笔记文档切分为携带层级路径信息的高质量 Chunk."""
        if not documents:
            return []

        docs_to_add = []
        for doc in documents:
            splits = self._split_markdown_hierarchical(doc.page_content, doc.metadata)
            
            for i, split_text in enumerate(splits):
                if not split_text.strip():
                    continue
                    
                meta = doc.metadata.copy() if doc.metadata else {}
                meta["chunk_index"] = i
                
                docs_to_add.append(Document(
                    page_content=split_text,
                    metadata=meta
                ))
                
        logger.info(f"原生 Markdown 树层级切片完成：将 {len(documents)} 篇笔记精细重构为 {len(docs_to_add)} 个结构化切片")
        return docs_to_add
        
    def _split_markdown_hierarchical(self, text: str, metadata: Dict[str, Any] = None) -> List[str]:
        """原生的、高精度 Markdown 树层级感知切片算法.
        
        该算法按行扫描 Markdown 文本：
        1. 实时提取并追踪当前的 `#` 到 `######` 标题树路径（例如：["MySQL部署", "配置索引", "全文本索引"]）。
        2. 在每一个打包的 Chunk 开头，前缀注入结构化的「知识路径链」前缀（例如：`# 知识节点: MySQL部署 > 配置索引 > 全文本索引\n\n`）。
        3. 控制 Chunk 字符大小，合并多段，预留 overlap，保留最本质的笔记结构上下文。
        """
        lines = text.split("\n")
        
        note_title = (metadata or {}).get("title", "").strip()
        note_path = (metadata or {}).get("path", "").strip()
        
        chunks = []
        current_headers: Dict[int, str] = {}  # 存储当前 level 到标题文本的映射
        current_text_buf: List[str] = []
        current_len = 0
        
        def make_path_prefix() -> str:
            path_parts = []
            if note_title:
                path_parts.append(note_title)
                
            # 顺着 1 到 6 级标题，把当前正生效的标题依次加入
            for lv in range(1, 7):
                if lv in current_headers and current_headers[lv]:
                    path_parts.append(current_headers[lv])
                    
            if not path_parts:
                return ""
                
            prefix = f"# 知识节点: {' > '.join(path_parts)}\n"
            if note_path:
                prefix += f"# 笔记归属: {note_path}\n"
            prefix += "---\n\n"
            return prefix

        for line_raw in lines:
            line = line_raw.strip()
            
            # 正则匹配 Markdown 标题：如 `# 标题一` 到 `###### 标题六`
            match_header = re.match(r"^(#{1,6})\s+(.*)$", line)
            if match_header:
                level = len(match_header.group(1))
                header_text = match_header.group(2).strip()
                
                # 遇到标题，先打包当前的缓冲区正文
                if current_text_buf:
                    content_body = "\n".join(current_text_buf).strip()
                    if content_body:
                        chunks.append(make_path_prefix() + content_body)
                    current_text_buf = []
                    current_len = 0
                
                # 更新当前标题层级路径。当高层标题出现时，清空其下的所有子级标题
                current_headers[level] = header_text
                for lv in list(current_headers.keys()):
                    if lv > level:
                        current_headers[lv] = ""
                continue
            
            # 段落正文处理
            if not line:
                if current_text_buf and current_text_buf[-1] != "":
                    current_text_buf.append("")  # 适当空行以保持格式
                continue
                
            current_text_buf.append(line_raw)
            current_len += len(line_raw) + 1
            
            # 如果加上路径前缀估算长度后，超出了 chunk_size
            if current_len >= (self.chunk_size - 180):
                content_body = "\n".join(current_text_buf).strip()
                if content_body:
                    chunks.append(make_path_prefix() + content_body)
                
                # 带有 overlap 缓冲区回退
                overlap_chars = 0
                overlap_buf = []
                for r_line in reversed(current_text_buf):
                    overlap_chars += len(r_line) + 1
                    if overlap_chars > self.chunk_overlap:
                        break
                    overlap_buf.insert(0, r_line)
                    
                current_text_buf = overlap_buf
                current_len = sum(len(l) + 1 for l in current_text_buf)

        # 兜底清空最后的缓冲区
        if current_text_buf:
            content_body = "\n".join(current_text_buf).strip()
            if content_body:
                chunks.append(make_path_prefix() + content_body)
                
        return chunks
