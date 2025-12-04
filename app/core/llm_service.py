# -*- coding: utf-8 -*-
"""Trilium知识体代理的语言模型服务."""

from app.core.config import Config
import os

# 尝试导入langchain组件
try:
    from langchain_community.llms import GPT4All
    LANGCHAIN_IMPORTED = True
except ImportError:
    LANGCHAIN_IMPORTED = False
    GPT4All = None


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
        if LANGCHAIN_IMPORTED and GPT4All:
            try:
                # 检查模型文件是否存在
                if not os.path.exists(self.config.llm_model_path):
                    print(f"模型文件不存在: {self.config.llm_model_path}")
                    self.llm = None
                    return
                    
                # 尝试使用当前版本的参数
                self.llm = GPT4All(
                    model=self.config.llm_model_path,
                    verbose=False
                )
                print("LLM初始化成功")
            except Exception as e:
                print(f"初始化LLM失败: {e}")
                # 尝试使用更简单的参数初始化
                try:
                    self.llm = GPT4All(model=self.config.llm_model_path)
                    print("LLM使用简化参数初始化成功")
                except Exception as e2:
                    print(f"再次尝试初始化LLM失败: {e2}")
                    self.llm = None
        else:
            print("Langchain不可用。LLM服务已禁用。")
    
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
        
        try:
            return self.llm.invoke(prompt)
        except Exception as e:
            print(f"生成文本时出错: {e}")
            return "生成响应时出错。"