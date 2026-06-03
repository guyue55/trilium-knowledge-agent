# -*- coding: utf-8 -*-
"""日常闲聊与知识库问答的前置意图路由器."""

import re
from loguru import logger


class IntentRouter:
    """RAG 前置意图分类决策器，实现日常闲聊 100% 拦截并跳过检索读库."""

    def __init__(self):
        # 1. 常见闲聊敏感正则
        self.chitchat_patterns = [
            # 常见中英文打招呼
            r"^(你好|您好|哈喽|早上好|中午好|下午好|晚上好|早安|午安|晚安|hello|hi|hey|hola|greetings|hi there)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
            # 身份询问
            r"^(你是谁|你叫什么|你叫什么名字|你是哪个大模型|你是大模型吗|你的作者是谁|谁创造了你|who are you|what is your name)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
            # 结束语、谢意
            r"^(谢谢|感谢|十分感谢|非常感谢|多谢|thank you|thanks|bye|byebye|再见|拜拜|告辞|下线)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
            # 无意义词或测试词
            r"^(测试|test|123|123456|啊啊啊|哦哦|哈哈|哈哈哈|呵呵|嗯嗯)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$"
        ]
        
        # 2. 强相关的专业/技术关键词，如果包含这些，哪怕字符数极短，也不认为是闲聊（防止误拦截）
        self.technical_keywords = [
            "mysql", "docker", "nginx", "trilium", "lancedb", "rag", "redis", "linux", "git", "bash", "python",
            "数据库", "缓存", "网络", "切片", "同步", "索引", "向量", "接口", "宿主机", "容器", "证书", "权限",
            "配置", "负载", "性能", "主从", "高可用", "备份", "恢复", "命令", "脚本", "说明", "路径", "部署"
        ]

    def classify(self, query: str) -> str:
        """判定问题意图.
        
        Args:
            query: 用户提问的文本.
            
        Returns:
            str: "CHITCHAT" (闲聊) 或 "KNOWLEDGE_QUERY" (知识检索)
        """
        if not query:
            return "CHITCHAT"
            
        clean_query = query.strip().lower()
        
        # 1. 极其简短的无意义问题（3个字以下且不含技术词），直接按闲聊处理
        if len(clean_query) <= 3:
            # 检查是否包含技术词
            has_tech = any(kw in clean_query for kw in self.technical_keywords)
            if not has_tech:
                logger.info(f"IntentRouter: 检测到极短非技术词 '{query}' -> 识别为 CHITCHAT")
                return "CHITCHAT"

        # 2. 正则表达式高频问候语/闲聊词典匹配
        for pattern in self.chitchat_patterns:
            if re.match(pattern, clean_query):
                # 再次防御：如果居然包含了某些强技术词，不拦截
                has_tech = any(kw in clean_query for kw in self.technical_keywords)
                if not has_tech:
                    logger.info(f"IntentRouter: 匹配到闲聊正则模式 -> '{query}' -> 识别为 CHITCHAT")
                    return "CHITCHAT"

        # 3. 默认流向 RAG 知识检索
        return "KNOWLEDGE_QUERY"
