# -*- coding: utf-8 -*-
"""Trilium知识体代理的语言模型服务."""

from app.core.config import Config
import os

# 尝试导入langchain组件
try:
    from langchain_community.llms import GPT4All
    from langchain_community.llms.tongyi import Tongyi
    LANGCHAIN_IMPORTED = True
except ImportError as e:
    print(f"导入langchain组件失败: {e}")
    LANGCHAIN_IMPORTED = False
    GPT4All = None
    Tongyi = None


class LLMService:
    """用于管理语言模型的服务."""
    
    def __init__(self, config: Config) -> None:
        """初始化LLM服务.
        
        Args:
            config: 应用程序配置.
        """
        self.config = config
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self) -> None:
        """初始化语言模型."""
        if not LANGCHAIN_IMPORTED:
            print("Langchain不可用。LLM服务已禁用。")
            return
            
        # 根据配置选择模型类型
        if self.config.llm_model_type.lower() == "qwen":
            self._initialize_qwen()
        else:
            self._initialize_gpt4all()
    
    def _initialize_gpt4all(self) -> None:
        """初始化GPT4All模型."""
        if not GPT4All:
            print("GPT4All组件不可用")
            self.llm = None
            return
            
        try:
            # 检查模型文件是否存在
            if not os.path.exists(self.config.llm_model_path):
                print(f"模型文件不存在: {self.config.llm_model_path}")
                print("请确保模型文件已下载到指定路径")
                self.llm = None
                return
                
            # 尝试使用当前版本的参数
            self.llm = GPT4All(
                model=self.config.llm_model_path,
                verbose=False
            )
            print("GPT4All LLM初始化成功")
        except Exception as e:
            print(f"初始化GPT4All LLM失败: {e}")
            # 尝试使用更简单的参数初始化
            try:
                self.llm = GPT4All(model=self.config.llm_model_path)
                print("GPT4All LLM使用简化参数初始化成功")
            except Exception as e2:
                print(f"再次尝试初始化GPT4All LLM失败: {e2}")
                self.llm = None
    
    def _initialize_qwen(self) -> None:
        """初始化阿里千问模型."""
        # 检查是使用API还是本地模型
        if self.config.qwen_api_key and self.config.qwen_api_key != "your_qwen_api_key_here":
            self._initialize_qwen_api()
        else:
            self._initialize_qwen_local()
    
    def _initialize_qwen_api(self) -> None:
        """初始化阿里千问API模型."""
        if not Tongyi:
            print("Tongyi组件不可用")
            self.llm = None
            return
            
        try:
            # 初始化千问模型
            self.llm = Tongyi(
                dashscope_api_key=self.config.qwen_api_key,
                model_name="qwen-turbo",
                client=None  # 显式传递client参数
            )
            print("阿里千问API LLM初始化成功")
        except Exception as e:
            print(f"初始化阿里千问API LLM失败: {e}")
            self.llm = None
    
    def _initialize_qwen_local(self) -> None:
        """初始化本地阿里千问模型."""
        try:
            # 检查本地模型是否存在
            if not os.path.exists(self.config.llm_model_path):
                print(f"本地Qwen模型不存在: {self.config.llm_model_path}")
                print("请确保模型文件已下载到指定路径")
                self.llm = None
                return
            
            # 尝试导入HuggingFacePipeline
            try:
                from langchain_community.llms.huggingface_pipeline import HuggingFacePipeline
                from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            except ImportError as e:
                print(f"导入HuggingFacePipeline组件失败: {e}")
                print("请安装必要依赖: pip install transformers")
                self.llm = None
                return
            
            print(f"正在加载本地Qwen模型: {self.config.llm_model_path}")
            
            # 加载分词器和模型
            tokenizer = AutoTokenizer.from_pretrained(
                self.config.llm_model_path, 
                trust_remote_code=True
            )
            model = AutoModelForCausalLM.from_pretrained(
                    self.config.llm_model_path, 
                    trust_remote_code=True
                )
            
            # 检查是否可以使用device_map和accelerate
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    self.config.llm_model_path, 
                    torch_dtype="auto",
                    device_map="auto",
                    trust_remote_code=True
                )
            except ImportError as e:
                print(f"警告: 无法使用device_map, 将在默认设备上加载模型: {e}")
                model = AutoModelForCausalLM.from_pretrained(
                    self.config.llm_model_path, 
                    trust_remote_code=True
                )
            
            # 创建pipeline
            try:
                pipe = pipeline(
                    "text-generation", 
                    model=model, 
                    tokenizer=tokenizer,
                    max_new_tokens=256
                )
            except Exception as e:
                print(f"创建pipeline时出错: {e}")
                # 尝试使用更基础的配置
                pipe = pipeline(
                    "text-generation", 
                    model=model, 
                    tokenizer=tokenizer
                )
            
            # 创建HuggingFacePipeline实例
            self.llm = HuggingFacePipeline(pipeline=pipe)
            
            print("本地Qwen模型加载成功")
        except Exception as e:
            print(f"初始化本地阿里千问LLM失败: {e}")
            import traceback
            traceback.print_exc()
            self.llm = None
    
    def get_llm(self):
        """获取语言模型实例.
        
        Returns:
            语言模型实例，如果未初始化则返回None.
        """
        return self.llm
    

    
    def generate_text(self, prompt: str) -> str:
        """使用语言模型生成文本.
        
        Args:
            prompt: 用于生成文本的提示.
            
        Returns:
            生成的文本.
        """
        if not self.llm:
            return "语言模型不可用。"
        
        # 本地Qwen模型现在通过HuggingFacePipeline实现，可以直接使用
        
        # 检查是否有invoke方法
        if hasattr(self.llm, 'invoke'):
            try:
                return getattr(self.llm, 'invoke')(prompt)
            except Exception as e:
                print(f"生成文本时出错: {e}")
                return "生成响应时出错。"
        else:
            return "语言模型不可用。"