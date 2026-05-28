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
            logger.error("无法导入 RecursiveCharacterTextSplitter")
            self.text_splitter = None

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
            splits = self.text_splitter.split_documents([doc])
            for split in splits:
                if not split.metadata:
                    split.metadata = {}
                
                # 继承和补全 Metadata
                title = doc.metadata.get("title", "未知标题")
                source = doc.metadata.get("source", "未知")
                note_id = doc.metadata.get("note_id", "")
                path = doc.metadata.get("path", "")

                split.metadata["title"] = title
                split.metadata["source"] = source
                split.metadata["note_id"] = note_id
                if path:
                    split.metadata["path"] = path

                # 元数据注入 (Metadata Injection): 将标题和路径信息直接编码到块文本的开头
                # 这会极大地提升向量检索在寻找具有特定限定词时的召回准确度
                header = f"标题: {title}\n"
                if path:
                    header += f"路径: {path}\n"
                header += "---\n"
                
                # 确保不重复注入
                if not split.page_content.startswith("标题: "):
                    split.page_content = header + split.page_content
            
            docs_to_add.extend(splits)
            
        return docs_to_add
