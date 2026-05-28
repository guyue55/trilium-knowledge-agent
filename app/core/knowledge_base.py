# -*- coding: utf-8 -*-
"""知识库管理服务."""

from __future__ import annotations

import os
import threading
from typing import Any

from loguru import logger

from app.core.config import Config, ConfigConstants

# 禁用 Chroma 的匿名遥测，避免 capture() 兼容性报错
os.environ.setdefault("CHROMA_TELEMETRY", "false")

# 使用社区版本导入路径

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

IMPORT_SUCCESS = True


class KnowledgeBase:
    """用于管理知识库的服务."""

    def __init__(self, config: Config) -> None:
        """初始化知识库.

        Args:
            config: 应用程序配置对象.
        """
        self.config = config
        self.embedding_model = None
        self.vector_store = None
        self.text_splitter = None
        self._db_lock = threading.Lock()  # 添加线程锁保护 ChromaDB 并发读写

        try:
            # 设置镜像源
            if self.config.hf_endpoint:
                os.environ["HF_ENDPOINT"] = self.config.hf_endpoint

            # 检查本地模型是否存在，如果不存在则自动下载
            model_name = self.config.embedding_model
            local_model_path = self.config.embedding_model_local_path

            if not os.path.exists(local_model_path):
                logger.info(f"本地模型不存在 ({local_model_path})，正在从镜像源自动下载...")
                try:
                    from huggingface_hub import snapshot_download

                    # 临时启用网络下载，覆盖环境变量设置
                    original_offline = os.environ.get("HF_HUB_OFFLINE")
                    if original_offline == "1":
                        logger.warning("检测到 HF_HUB_OFFLINE=1，正在临时启用网络以进行下载...")
                        os.environ["HF_HUB_OFFLINE"] = "0"

                    # 设置镜像源
                    # if not os.environ.get('HF_ENDPOINT'):
                    #     os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

                    # # 确保在下载前再次强制设置，防止被其他库重置
                    # os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

                    logger.info(f"正在下载模型 {model_name} 到 {local_model_path} ...")
                    logger.info(f"使用镜像源: {os.environ['HF_ENDPOINT']}")

                    snapshot_download(
                        repo_id=model_name,
                        local_dir=local_model_path,
                        local_dir_use_symlinks=False,
                        resume_download=True,
                        # endpoint="https://hf-mirror.com"  # 显式传递endpoint参数
                    )
                    logger.info("模型下载完成")

                    # 恢复环境变量（如果之前有设置）
                    if original_offline is not None:
                        os.environ["HF_HUB_OFFLINE"] = original_offline

                    # 更新模型名称为本地路径
                    model_name = local_model_path
                except ImportError:
                    logger.error("错误: 未安装 huggingface_hub，无法自动下载模型")
                    logger.error("请运行: pip install huggingface_hub")
                except Exception as e:
                    logger.error(f"模型下载失败: {e}")
                    logger.warning("将尝试直接从在线源加载...")
            else:
                logger.info(f"使用本地嵌入模型: {local_model_path}")
                model_name = local_model_path

            # 使用本地缓存的模型，避免网络连接问题
            try:
                self.embedding_model = HuggingFaceEmbeddings(model_name=model_name, cache_folder="./data/models")
                logger.info("嵌入模型初始化成功")
            except RuntimeError as re:
                if "split_torch_state_dict_into_shards" in str(re):
                    logger.warning("检测到huggingface_hub版本兼容性问题，尝试使用降级方案...")
                    # 版本兼容性问题的特殊处理
                    try:
                        # 使用更简单的初始化方式
                        self.embedding_model = HuggingFaceEmbeddings(
                            model_name=model_name,
                            cache_folder="./data/models",
                            model_kwargs={"local_files_only": True},  # 只使用本地文件
                        )
                        logger.info("使用本地文件模式初始化嵌入模型成功")
                    except Exception as e2:
                        logger.error(f"本地文件模式初始化也失败: {e2}")
                        self.embedding_model = None
                else:
                    logger.error(f"嵌入模型初始化出现运行时错误: {re}")
                    self.embedding_model = None
            except Exception as e:
                logger.error(f"嵌入模型初始化出现其他错误: {e}")
                self.embedding_model = None

            if self.embedding_model:
                try:
                    self.vector_store = Chroma(
                        embedding_function=self.embedding_model,
                        persist_directory=config.vector_db_dir,
                    )
                    logger.info("向量存储初始化成功")
                except Exception as e:
                    logger.error(f"向量存储初始化失败: {e}")
                    self.vector_store = None
            else:
                logger.error("嵌入模型未正确初始化，向量存储也无法初始化")
                self.vector_store = None

            # 只有在需要时才初始化文本分割器
            # 优化：添加针对中文的分隔符，确保语义完整性
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
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
            logger.info(f"文本分割器初始化成功 (chunk_size={config.chunk_size}, chunk_overlap={config.chunk_overlap})")
        except Exception as e:
            logger.error(f"初始化知识库组件时出错: {e}")
            logger.exception("详细错误信息")
            self.embedding_model = None
            self.vector_store = None
            self.text_splitter = None

    def clear_vector_store(self) -> None:
        """清空向量数据库.

        删除现有的集合并重新创建一个空的。
        """
        if not IMPORT_SUCCESS or not self.vector_store:
            logger.error("向量存储未正确初始化")
            return

        try:
            logger.info("正在清空向量数据库...")
            with self._db_lock:
                # 删除集合
                self.vector_store.delete_collection()

                # 重新初始化向量存储
                self.vector_store = Chroma(
                    embedding_function=self.embedding_model,
                    persist_directory=self.config.vector_db_dir,
                )
                self.vector_store.persist()
            logger.info("向量数据库已成功清空")
        except Exception as e:
            logger.error(f"清空向量数据库时出错: {e}")
            logger.exception("详细错误信息")

    def update_vector_store(self, documents: list[Any]) -> None:
        """更新向量数据库.

        Args:
            documents: 要添加到向量存储的文档列表.
        """
        # 延迟初始化文本分割器
        if not self.text_splitter and RecursiveCharacterTextSplitter:
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

        if not IMPORT_SUCCESS or self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return

        try:
            # 准备文档列表
            docs_to_add = []

            # 如果没有文本分割器，直接使用原始文档
            if not self.text_splitter:
                docs_to_add = documents
            else:
                # 分割每个文档
                for doc in documents:
                    # 分割文档
                    splits = self.text_splitter.split_documents([doc])
                    # 为每个分割后的文档添加元数据
                    for split in splits:
                        # 确保元数据包含所有必要信息
                        if not split.metadata:
                            split.metadata = {}

                        # 从原始文档复制元数据
                        split.metadata["title"] = doc.metadata.get("title", "未知标题")
                        split.metadata["source"] = doc.metadata.get("source", "未知")
                        split.metadata["note_id"] = doc.metadata.get("note_id", "")

                        # 如果有路径信息也添加到元数据中
                        if "path" in doc.metadata:
                            split.metadata["path"] = doc.metadata["path"]

                        logger.debug(
                            f"为文档片段添加元数据: title={split.metadata['title']}, "
                            f"note_id={split.metadata['note_id']}, path={split.metadata.get('path', '无')}"
                        )

                    docs_to_add.extend(splits)

            # 更新向量数据库
            if docs_to_add:  # 确保有文档要添加
                total_docs = len(docs_to_add)
                # ChromaDB has a batch size limit (around 41666), so we process in smaller batches
                batch_size = ConfigConstants.VECTOR_DB_BATCH_SIZE
                logger.info(f"准备添加 {total_docs} 个文档片段到向量存储，分批处理 (每批 {batch_size})...")

                for i in range(0, total_docs, batch_size):
                    batch = docs_to_add[i : i + batch_size]
                    current_batch_num = i // batch_size + 1
                    total_batches = (total_docs + batch_size - 1) // batch_size
                    logger.info(
                        f"正在处理批次 {current_batch_num}/{total_batches} (文档片段 {i + 1} - {min(i + batch_size, total_docs)})..."
                    )

                    with self._db_lock:
                        self.vector_store.add_documents(batch)

                        # 优化：只在最后一批或每3批时persist，减少I/O操作
                        if hasattr(self.vector_store, "persist"):
                            # 如果是最后一批，或者每3批，进行持久化
                            if (current_batch_num == total_batches) or (current_batch_num % 3 == 0):
                                self.vector_store.persist()
                                logger.debug(f"批次 {current_batch_num} 已持久化到磁盘")

                logger.info(f"成功添加所有 {total_docs} 个文档片段到向量存储")
            else:
                logger.info("没有文档需要添加到向量存储")
        except Exception as e:
            logger.error(f"更新向量存储时出错: {e}")
            logger.exception("详细错误信息")

    async def semantic_search_async(self, query: str, k: int = 5, filter: dict[str, Any] | None = None) -> list[Any]:
        """异步版本的语义搜索.

        Args:
            query: 搜索查询字符串.
            k: 要返回的结果数量.
            filter: 可选的元数据过滤器.

        Returns:
            list[Any]: 相关文档列表.
        """
        import asyncio

        return await asyncio.to_thread(self.semantic_search, query, k=k, filter=filter)

    def semantic_search(self, query: str, k: int = 5, filter: dict[str, Any] | None = None) -> list[Any]:
        """执行语义搜索以查找相关文档.

        Args:
            query: 搜索查询字符串.
            k: 要返回的结果数量，默认为5.
            filter: 可选的元数据过滤器.

        Returns:
            list[Any]: 相关文档列表，如果失败则返回空列表.
        """

        if not IMPORT_SUCCESS or not self.vector_store:
            logger.error("向量存储未正确初始化")
            return []

        try:
            with self._db_lock:
                return self.vector_store.similarity_search(query, k=k, filter=filter)
        except Exception as e:
            logger.error(f"语义搜索时出错: {e}")
            logger.exception("详细错误信息")
            return []

    def cleanup(self) -> None:
        """清理资源，关闭连接."""
        try:
            if self.vector_store:
                logger.info("正在关闭向量数据库连接...")
                # Chroma 通常在销毁时自动持久化，但我们可以显式调用
                if hasattr(self.vector_store, "persist"):
                    self.vector_store.persist()
                self.vector_store = None

            if self.embedding_model:
                logger.info("正在释放嵌入模型资源...")
                self.embedding_model = None

            logger.info("知识库资源清理完成")
        except Exception as e:
            logger.error(f"清理知识库资源时出错: {e}")
