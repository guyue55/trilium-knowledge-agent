# -*- coding: utf-8 -*-
"""知识库管理服务."""

from app.core.config import Config
import os


# 使用社区版本导入路径
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
IMPORT_SUCCESS = True
# # 尝试导入langchain组件
# try:
#     # 使用社区版本导入路径
#     from langchain_community.embeddings import HuggingFaceEmbeddings
#     from langchain_community.vectorstores import Chroma
#     from langchain.text_splitter import RecursiveCharacterTextSplitter
#     IMPORT_SUCCESS = True
# except ImportError as e:
#     print(f"无法导入langchain组件: {e}")
#     IMPORT_SUCCESS = False
#     HuggingFaceEmbeddings = None
#     Chroma = None
#     RecursiveCharacterTextSplitter = None


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
        
        if IMPORT_SUCCESS and HuggingFaceEmbeddings and Chroma:
            try:
                # 设置镜像源
                if self.config.hf_endpoint:
                    os.environ['HF_ENDPOINT'] = self.config.hf_endpoint
                
                # 检查本地模型是否存在，如果不存在则使用在线模型
                model_name = self.config.embedding_model
                local_model_path = self.config.embedding_model_local_path
                if os.path.exists(local_model_path):
                    model_name = local_model_path
                    print(f"使用本地嵌入模型: {model_name}")
                else:
                    print(f"警告: 本地模型不存在 ({local_model_path})")
                    print(f"将从在线源加载模型: {model_name}")
                    # 检查是否有网络连接，如果没有给出明确提示
                    try:
                        import requests
                        requests.get("https://huggingface.co", timeout=5)
                    except:
                        print("警告: 无法连接到Hugging Face，可能需要配置代理或使用镜像源")
                
                # 使用本地缓存的模型，避免网络连接问题
                self.embedding_model = HuggingFaceEmbeddings(
                    model_name=model_name,
                    cache_folder="./data/models"
                )
                print("嵌入模型初始化成功")
                
                self.vector_store = Chroma(
                    embedding_function=self.embedding_model,
                    persist_directory=config.vector_db_dir
                )
                print("向量存储初始化成功")
                
                # 只有在需要时才初始化文本分割器
                # self.text_splitter = RecursiveCharacterTextSplitter(
                #     chunk_size=1000,
                #     chunk_overlap=200
                # )
                # print("文本分割器初始化成功")
            except Exception as e:
                print(f"初始化知识库组件时出错: {e}")
                import traceback
                traceback.print_exc()
                self.embedding_model = None
                self.vector_store = None
                self.text_splitter = None
        else:
            print("缺少必要的Langchain组件")
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
                chunk_size=1000,
                chunk_overlap=200
            )
            
        if not IMPORT_SUCCESS or self.vector_store is None:
            print("向量存储未正确初始化")
            return
            
        try:
            # 如果没有文本分割器，直接使用原始文档
            if self.text_splitter:
                # 分割文档
                texts = self.text_splitter.split_documents(documents)
            else:
                # 直接使用原始文档
                texts = documents

            # 更新向量数据库
            if texts:  # 确保有文档要添加
                self.vector_store.add_documents(texts)
                self.vector_store.persist()
                print(f"成功添加 {len(texts)} 个文档到向量存储")
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