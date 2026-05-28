# -*- coding: utf-8 -*-
"""Trilium integration service."""

from __future__ import annotations

import html
import time
from typing import Any

import requests
import trilium_py.client
from bs4 import BeautifulSoup
from loguru import logger
from requests.adapters import HTTPAdapter
from trilium_py.client import ETAPI
from urllib3.util.retry import Retry

from app.core.config import Config, ConfigConstants


# Monkey patch trilium_py to use a shared session with retry logic
# This prevents WinError 10048 (socket exhaustion) by reusing TCP connections
def get_session() -> requests.Session:
    """创建带有重试策略的共享Session.

    Returns:
        requests.Session: 配置了连接池和重试策略的Session对象.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=ConfigConstants.DEFAULT_MAX_RETRIES,
        backoff_factor=ConfigConstants.DEFAULT_RETRY_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,  # Increase pool size
        pool_maxsize=20,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# Apply monkey patch
shared_session = get_session()
trilium_py.client.requests = shared_session


class TriliumService:
    """Service for interacting with Trilium Notes."""

    def __init__(self, config: Config):
        """Initialize the service.

        Args:
            config: Application configuration
        """
        self.config = config
        self.client: ETAPI | None = None
        self.note_ids = config.note_ids
        self.depth = config.depth
        self.limit = config.limit
        self._connect()

    def _connect(self) -> None:
        """建立到Trilium ETAPI的连接."""
        try:
            logger.info(f"Connecting to Trilium at {self.config.trilium_base_url}...")
            self.client = ETAPI(self.config.trilium_base_url, self.config.trilium_token)
            # Verify connection by getting app info or root note
            try:
                app_info = self.client.app_info()
                logger.info(f"Successfully connected to Trilium. app_info： {app_info}")
            except Exception:
                logger.warning("Warning: Could not verify Trilium connection (app_info failed).")
        except Exception as e:
            logger.error(f"Failed to connect to Trilium: {e}")
            self.client = None

    def load_documents(self) -> list[dict[str, Any]]:
        """Load documents from Trilium.

        Returns:
            List of documents (dictionaries)
        """
        documents: list[dict[str, Any]] = []
        if self.client:
            self._try_load_real_documents(documents)
        else:
            logger.error("No Trilium connection, returning empty list.")
        return documents

    def _try_load_real_documents(self, documents: list[dict[str, Any]]) -> None:
        """Try to load real documents from Trilium using BFS with filtering.

        Args:
            documents: List to append loaded documents to
        """

        if not self.client:
            return

        try:
            note_ids_to_process = self.note_ids
            logger.info(f"Preparing to load documents from note IDs: {note_ids_to_process}")

            total_processed = 0
            total_skipped = 0
            total_errors = 0

            # Binary/Non-text MIME types to skip
            binary_types = [
                "image",
                "application/pdf",
                "application/zip",
                "application/octet-stream",
                "application/x-zip-compressed",
                "application/x-compressed",
                "application/x-tar",
                "application/gzip",
                "application/x-gzip",
                "application/x-7z-compressed",
                "application/x-rar-compressed",
            ]

            for root_note_id in note_ids_to_process:
                logger.info(f"\n=== Processing Root Note ID: {root_note_id} ===")

                # Custom BFS traversal
                from collections import deque

                queue = deque([(root_note_id, 1)])  # (note_id, depth)
                visited = {root_note_id}

                processed_count = 0
                skipped_count = 0
                error_count = 0

                while queue:
                    # Check for global limit
                    if len(documents) >= self.limit:
                        logger.warning(f"Reached maximum document limit: {self.limit}")
                        break
                        
                    # Check for queue explosion
                    if len(queue) > 10000:
                        logger.warning("Queue size exceeded 10000. Aborting BFS to prevent OOM.")
                        break

                    current_note_id, current_depth = queue.popleft()

                    # Progress log every 50 scanned items
                    total_scanned = processed_count + skipped_count + error_count
                    if total_scanned > 0 and total_scanned % 50 == 0:
                        logger.info(
                            f"Progress: Scanned {total_scanned} notes (Collected: {len(documents)}, Skipped: {skipped_count}, Queue: {len(queue)})..."
                        )

                    # Add small delay to regulate request rate
                    time.sleep(0.01)  # 10ms delay

                    # Retry logic for network operations
                    max_retries = 5  # Increased retries
                    retry_delay = 2

                    try:
                        # Get note details. The shared session already handles retries for network errors.
                        note = self.client.get_note(current_note_id)
                        if not note:
                            error_count += 1
                            continue
                    except Exception as e:
                        logger.error(f"Failed to get note {current_note_id}: {e}")
                        error_count += 1
                        continue

                        # Handle legacy format if needed
                        if "note" in note and "noteId" not in note:
                            note = note["note"]

                        title = note.get("title", "Untitled")
                        note_type = note.get("type", "text")
                        mime = note.get("mime", "")

                        # 1. 预过滤：跳过非文本类型和二进制内容
                        should_process_content = True
                        if note_type not in ConfigConstants.VALID_NOTE_TYPES:
                            logger.debug(f"跳过非文本类型笔记: {title} (类型: {note_type})")
                            should_process_content = False
                            skipped_count += 1
                        elif mime in binary_types or any(
                            mime.startswith(prefix) for prefix in ConfigConstants.BINARY_MIME_PREFIXES
                        ):
                            logger.debug(f"跳过二进制MIME类型笔记: {title} (MIME: {mime})")
                            should_process_content = False
                            skipped_count += 1

                        # 2. Fetch content if valid text type
                        if should_process_content:
                            content = ""
                            try:
                                content_response = self.client.get_note_content(current_note_id)

                                if content_response:
                                    if isinstance(content_response, str):
                                        content = content_response
                                    elif isinstance(content_response, bytes):
                                        # Multi-encoding fallback
                                        try:
                                            content = content_response.decode("utf-8")
                                        except UnicodeDecodeError:
                                            try:
                                                content = content_response.decode("gbk")
                                            except UnicodeDecodeError:
                                                try:
                                                    content = content_response.decode("latin1")
                                                except UnicodeDecodeError:
                                                    logger.warning(f"Skipping undecodable content: {title}")
                                    else:
                                        content = str(content_response)
                            except Exception as e:
                                logger.error(f"Error fetching content for {current_note_id}: {e}")

                            # 3. Add to documents if content is valid
                            if content:
                                # Clean HTML content
                                try:
                                    # First unescape HTML entities
                                    content = html.unescape(content)
                                    # Then strip HTML tags using BeautifulSoup
                                    # We use a newline separator to preserve paragraph structure for better chunking
                                    soup = BeautifulSoup(content, "html.parser")
                                    content = soup.get_text(separator="\n", strip=True)
                                except Exception as e:
                                    logger.warning(f"Warning: Failed to clean HTML for note {current_note_id}: {e}")
                                    # Fallback to original content if cleaning fails

                            # 3. 验证内容有效性并添加到文档列表
                            if content and len(content.strip()) > ConfigConstants.MIN_CONTENT_LENGTH:
                                documents.append(
                                    {
                                        "content": content.strip(),
                                        "title": title,
                                        "note_id": current_note_id,
                                        "attributes": [],
                                        "type": note_type,
                                        "mime": mime,
                                    }
                                )
                                logger.debug(f"✅ [{processed_count + 1}] 成功添加笔记: {title}")
                                processed_count += 1
                            else:
                                logger.debug(
                                    f"跳过内容过短的笔记: {title} (长度: {len(content.strip()) if content else 0})"
                                )
                                skipped_count += 1

                        # 4. Enqueue children
                        if current_depth < self.depth:
                            child_ids = note.get("childNoteIds", [])
                            for child_id in child_ids:
                                if child_id not in visited:
                                    visited.add(child_id)
                                    queue.append((child_id, current_depth + 1))

                    except KeyboardInterrupt:
                        raise  # Re-raise to be handled by caller
                    except Exception as e:
                        logger.error(f"Error processing note {current_note_id}: {e}")
                        error_count += 1

                total_processed += processed_count
                total_skipped += skipped_count
                total_errors += error_count

                logger.info(f"\n=== Root Note {root_note_id} Finished ===")
                logger.info(f"Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")

            logger.info("\n🎯 Total Results:")
            logger.info(f"Total Processed: {total_processed}")
            logger.info(f"Total Skipped: {total_skipped}")
            logger.info(f"Total Errors: {total_errors}")
            logger.info(f"Final Document Count: {len(documents)}")

        except KeyboardInterrupt:
            logger.warning("\nOperation interrupted by user.")
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            logger.exception("详细错误信息")
            raise

    def cleanup(self) -> None:
        """清理资源，关闭会话."""
        try:
            # shared_session 是全局的，但在服务关闭时应该被关闭
            global shared_session
            if shared_session:
                logger.info("正在关闭 Trilium 共享 Session...")
                shared_session.close()
            logger.info("Trilium 资源清理完成")
        except Exception as e:
            logger.error(f"清理 Trilium 资源时出错: {e}")
