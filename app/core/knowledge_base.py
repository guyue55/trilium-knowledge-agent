# -*- coding: utf-8 -*-
"""知识库管理服务."""

from app.core.config import Config
import os


# 使用社区版本导入路径
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
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
        
        try:
            # 设置镜像源
            if self.config.hf_endpoint:
                os.environ['HF_ENDPOINT'] = self.config.hf_endpoint
            
            # 检查本地模型是否存在，如果不存在则自动下载
            model_name = self.config.embedding_model
            local_model_path = self.config.embedding_model_local_path
            
            if not os.path.exists(local_model_path):
                print(f"本地模型不存在 ({local_model_path})，正在从镜像源自动下载...")
                try:
                    from huggingface_hub import snapshot_download
                    
                    # 临时启用网络下载，覆盖环境变量设置
                    original_offline = os.environ.get('HF_HUB_OFFLINE')
                    if original_offline == '1':
                        print("检测到 HF_HUB_OFFLINE=1，正在临时启用网络以进行下载...")
                        os.environ['HF_HUB_OFFLINE'] = '0'
                    
                    # 设置镜像源
                    # if not os.environ.get('HF_ENDPOINT'):
                    #     os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
                    
                    # # 确保在下载前再次强制设置，防止被其他库重置
                    # os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
                    
                    print(f"正在下载模型 {model_name} 到 {local_model_path} ...")
                    print(f"使用镜像源: {os.environ['HF_ENDPOINT']}")
                    
                    snapshot_download(
                        repo_id=model_name,
                        local_dir=local_model_path,
                        local_dir_use_symlinks=False,
                        resume_download=True,
                        # endpoint="https://hf-mirror.com"  # 显式传递endpoint参数
                    )
                    print("模型下载完成")
                    
                    # 恢复环境变量（如果之前有设置）
                    if original_offline is not None:
                        os.environ['HF_HUB_OFFLINE'] = original_offline
                    
                    # 更新模型名称为本地路径
                    model_name = local_model_path
                except ImportError:
                    print("错误: 未安装 huggingface_hub，无法自动下载模型")
                    print("请运行: pip install huggingface_hub")
                except Exception as e:
                    print(f"模型下载失败: {e}")
                    print("将尝试直接从在线源加载...")
            else:
                print(f"使用本地嵌入模型: {local_model_path}")
                model_name = local_model_path
            
            # 使用本地缓存的模型，避免网络连接问题
            try:
                self.embedding_model = HuggingFaceEmbeddings(
                    model_name=model_name,
                    cache_folder="./data/models"
                )
                print("嵌入模型初始化成功")
            except RuntimeError as re:
                if "split_torch_state_dict_into_shards" in str(re):
                    print("检测到huggingface_hub版本兼容性问题，尝试使用降级方案...")
                    # 版本兼容性问题的特殊处理
                    try:
                        # 使用更简单的初始化方式
                        self.embedding_model = HuggingFaceEmbeddings(
                            model_name=model_name,
                            cache_folder="./data/models",
                            model_kwargs={"local_files_only": True}  # 只使用本地文件
                        )
                        print("使用本地文件模式初始化嵌入模型成功")
                    except Exception as e2:
                        print(f"本地文件模式初始化也失败: {e2}")
                        self.embedding_model = None
                else:
                    print(f"嵌入模型初始化出现运行时错误: {re}")
                    self.embedding_model = None
            except Exception as e:
                print(f"嵌入模型初始化出现其他错误: {e}")
                self.embedding_model = None
            
            if self.embedding_model:
                try:
                    self.vector_store = Chroma(
                        embedding_function=self.embedding_model,
                        persist_directory=config.vector_db_dir
                    )
                    print("向量存储初始化成功")
                except Exception as e:
                    print(f"向量存储初始化失败: {e}")
                    self.vector_store = None
            else:
                print("嵌入模型未正确初始化，向量存储也无法初始化")
                self.vector_store = None
            
            # 只有在需要时才初始化文本分割器
            # 增加 chunk_size 和 chunk_overlap 以保留更完整的上下文
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000,
                chunk_overlap=500
            )
            print("文本分割器初始化成功")
        except Exception as e:
            print(f"初始化知识库组件时出错: {e}")
            import traceback
            traceback.print_exc()
            self.embedding_model = None
            self.vector_store = None
            self.text_splitter = None
    
    def clear_vector_store(self) -> None:
        """清空向量数据库.
        
        删除现有的集合并重新创建一个空的。
        """
        if not IMPORT_SUCCESS or not self.vector_store:
            print("向量存储未正确初始化")
            return
            
        try:
            print("正在清空向量数据库...")
            # 删除集合
            self.vector_store.delete_collection()
            
            # 重新初始化向量存储
            self.vector_store = Chroma(
                embedding_function=self.embedding_model,
                persist_directory=self.config.vector_db_dir
            )
            self.vector_store.persist()
            print("向量数据库已成功清空")
        except Exception as e:
            print(f"清空向量数据库时出错: {e}")
            import traceback
            traceback.print_exc()

    def update_vector_store(self, documents) -> None:
        """更新向量数据库.
        
        Args:
            documents: 要添加到向量存储的文档.
        """
        # 延迟初始化文本分割器
        if not self.text_splitter and RecursiveCharacterTextSplitter:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000,
                chunk_overlap=500
            )
            
        if not IMPORT_SUCCESS or self.vector_store is None:
            print("向量存储未正确初始化")
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
                        split.metadata['title'] = doc.metadata.get('title', '未知标题')
                        split.metadata['source'] = doc.metadata.get('source', '未知')
                        split.metadata['note_id'] = doc.metadata.get('note_id', '')
                        
                        # 如果有路径信息也添加到元数据中
                        if 'path' in doc.metadata:
                            split.metadata['path'] = doc.metadata['path']
                        # print(f"为文档片段添加元数据: title={split.metadata['title']}, "
                        #       f"note_id={split.metadata['note_id']}, path={split.metadata.get('path', '无')}")
                    
                    docs_to_add.extend(splits)

            # 更新向量数据库
            if docs_to_add:  # 确保有文档要添加
                total_docs = len(docs_to_add)
                # ChromaDB has a batch size limit (around 41666), so we process in smaller batches
                batch_size = 5000
                print(f"准备添加 {total_docs} 个文档片段到向量存储，分批处理 (每批 {batch_size})...")
                
                for i in range(0, total_docs, batch_size):
                    batch = docs_to_add[i:i + batch_size]
                    current_batch_num = i // batch_size + 1
                    total_batches = (total_docs + batch_size - 1) // batch_size
                    print(f"正在处理批次 {current_batch_num}/{total_batches} (文档片段 {i+1} - {min(i+batch_size, total_docs)})...")
                    
                    self.vector_store.add_documents(batch)
                    
                    # Persist after each batch to save progress
                    if hasattr(self.vector_store, 'persist'):
                        self.vector_store.persist()
                        
                print(f"成功添加所有 {total_docs} 个文档片段到向量存储")
            else:
                print("没有文档需要添加到向量存储")
        except Exception as e:
            print(f"更新向量存储时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def semantic_search(self, query: str, k: int = 5):
        """执行语义搜索以查找相关文档.
        
        Args:
            query: 搜索查询.
            k: 要返回的结果数量.
            
        Returns:
            相关文档列表.
        """
        if not IMPORT_SUCCESS or not self.vector_store:
            print("向量存储未正确初始化")
            return []
            
        try:
            return self.vector_store.similarity_search(query, k=k)
        except Exception as e:
            print(f"语义搜索时出错: {e}")
            import traceback
            traceback.print_exc()
            return []