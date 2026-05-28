# -*- coding: utf-8 -*-
"""Trilium 笔记爬取与内容提取."""

import html
import time
from collections import deque
from typing import Any, List

from bs4 import BeautifulSoup
from loguru import logger

from app.core.config import Config, ConfigConstants
from app.trilium.client import TriliumClient


class TriliumCrawler:
    """负责通过 BFS 遍历知识树，抓取并清理笔记内容."""

    def __init__(self, config: Config, client: TriliumClient):
        self.config = config
        self.client = client
        self.note_ids = config.note_ids
        self.depth = config.depth
        self.limit = config.limit

    def load_documents(self) -> List[Dict[str, Any]]:
        if not self.client.is_connected():
            logger.error("Trilium 未连接，返回空列表")
            return []

        documents = []
        try:
            self._bfs_crawl(documents)
        except Exception as e:
            logger.error(f"加载文档时发生严重错误: {e}")
        return documents

    def _bfs_crawl(self, documents: List[Dict[str, Any]]) -> None:
        binary_types = [
            "image", "application/pdf", "application/zip", 
            "application/octet-stream", "application/x-zip-compressed",
            "application/x-compressed", "application/x-tar", "application/gzip",
            "application/x-7z-compressed", "application/x-rar-compressed"
        ]

        total_processed = 0
        total_skipped = 0
        total_errors = 0

        for root_note_id in self.note_ids:
            logger.info(f"\n=== 开始处理 Root Note ID: {root_note_id} ===")
            
            queue = deque([(root_note_id, 1)])
            visited = {root_note_id}

            processed_count = 0
            skipped_count = 0
            error_count = 0

            while queue:
                if len(documents) >= self.limit:
                    logger.warning(f"达到文档抓取数量上限: {self.limit}")
                    break
                if len(queue) > 10000:
                    logger.warning("BFS 队列超过 10000，触发 OOM 保护熔断。")
                    break

                current_note_id, current_depth = queue.popleft()
                time.sleep(0.01)

                try:
                    # 1. 获取笔记元数据
                    note = self.client.api.get_note(current_note_id)
                    if not note:
                        error_count += 1
                        continue
                except Exception as e:
                    logger.error(f"获取笔记 {current_note_id} 失败: {e}")
                    error_count += 1
                    continue

                if "note" in note and "noteId" not in note:
                    note = note["note"]

                title = note.get("title", "Untitled")
                note_type = note.get("type", "text")
                mime = note.get("mime", "")

                # 过滤不合法或二进制类型
                if note_type not in ConfigConstants.VALID_NOTE_TYPES or mime in binary_types or any(mime.startswith(p) for p in ConfigConstants.BINARY_MIME_PREFIXES):
                    skipped_count += 1
                else:
                    # 2. 获取笔记内容
                    try:
                        content_response = self.client.api.get_note_content(current_note_id)
                        content = self._decode_content(content_response)
                        
                        if content:
                            content = self._clean_html(content)
                            
                        if content and len(content.strip()) > ConfigConstants.MIN_CONTENT_LENGTH:
                            documents.append({
                                "content": content.strip(),
                                "title": title,
                                "note_id": current_note_id,
                                "attributes": [],
                                "type": note_type,
                                "mime": mime,
                            })
                            processed_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        logger.error(f"获取笔记 {title} 内容失败: {e}")
                        error_count += 1

                # 3. 子节点入队
                if current_depth < self.depth:
                    child_ids = note.get("childNoteIds", [])
                    for child_id in child_ids:
                        if child_id not in visited:
                            visited.add(child_id)
                            queue.append((child_id, current_depth + 1))

            total_processed += processed_count
            total_skipped += skipped_count
            total_errors += error_count

            logger.info(f"Root {root_note_id} 爬取完毕 -> 成功: {processed_count}, 跳过: {skipped_count}, 错误: {error_count}")

        logger.info(f"最终文档数: {len(documents)}")

    def _decode_content(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, bytes):
            for encoding in ['utf-8', 'gbk', 'latin1']:
                try:
                    return response.decode(encoding)
                except UnicodeDecodeError:
                    pass
        return str(response)

    def _clean_html(self, raw_html: str) -> str:
        try:
            unescaped = html.unescape(raw_html)
            soup = BeautifulSoup(unescaped, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return raw_html
