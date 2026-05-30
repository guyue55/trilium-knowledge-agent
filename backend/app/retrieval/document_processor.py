# -*- coding: utf-8 -*-
"""文档处理与切分."""

from typing import Any, List

from loguru import logger

from app.core.config import Config


class DocumentProcessor:
    """负责将原始文档进行切块（Chunking）和清洗."""

    def __init__(self, config: Config):
        self.config = config
        self.text_splitter = None
        self._init_splitter()

    def _init_splitter(self) -> None:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain.text_splitter import MarkdownHeaderTextSplitter

            self.headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
                ("####", "Header 4"),
            ]
            self.markdown_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=self.headers_to_split_on,
                strip_headers=False
            )

            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                separators=[
                    "\n\n",
                    "\n",
                    "。",
                    "！",
                    "？",
                    "；",
                    "．",
                    ".",
                    "!",
                    "?",
                    ";",
                    " ",
                    "",
                ],
            )
            logger.info(f"文档切分器初始化成功 (chunk_size={self.config.chunk_size})")
        except ImportError:
            logger.error("无法导入切分器相关的 Langchain 依赖")
            self.text_splitter = None
            self.markdown_splitter = None

    def split_documents(self, documents: List[Any]) -> List[Any]:
        """切分文档并继承元数据.
        
        Args:
            documents: 原始文档列表
            
        Returns:
            List[Any]: 切分后的文档片段列表
        """
        if not self.text_splitter:
            logger.warning("文本切分器不可用，将返回原始文档")
            return documents

        docs_to_add = []
        for doc in documents:
            # 1. 结构感知切割：按 Markdown 标题分块
            try:
                md_splits = self.markdown_splitter.split_text(doc.page_content)
                # 继承原文档元数据
                for md_split in md_splits:
                    for k, v in doc.metadata.items():
                        if k not in md_split.metadata:
                            md_split.metadata[k] = v
            except Exception as e:
                logger.warning(f"Markdown 切分失败: {e}，将直接进行长度切分")
                md_splits = [doc]

            # 2. 长度截断切割：防止单个章节过长
            splits = self.text_splitter.split_documents(md_splits)
            
            for split in splits:
                if not split.metadata:
                    split.metadata = {}
                
                # 继承和补全 Metadata
                title = split.metadata.get("title", "未知标题")
                source = split.metadata.get("source", "未知")
                note_id = split.metadata.get("note_id", "")
                path = split.metadata.get("path", "")

                # 收集 Markdown 层级章节结构
                headers = []
                for i in range(1, 5):
                    h_val = split.metadata.get(f"Header {i}")
                    if h_val:
                        headers.append(h_val)
                header_context = " > ".join(headers)

                split.metadata["title"] = title
                split.metadata["source"] = source
                split.metadata["note_id"] = note_id
                if path:
                    split.metadata["path"] = path

                # 元数据注入 (Metadata Injection): 将标题、路径、章节信息直接编码到块文本的开头
                header = f"标题: {title}\n"
                if path:
                    header += f"路径: {path}\n"
                if header_context:
                    header += f"章节: {header_context}\n"
                header += "---\n"
                
                # 确保不重复注入
                if not split.page_content.startswith("标题: "):
                    split.page_content = header + split.page_content
            
            docs_to_add.extend(splits)
            
        return docs_to_add
