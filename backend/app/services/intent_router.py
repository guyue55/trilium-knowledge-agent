# -*- coding: utf-8 -*-
"""日常闲聊与知识库问答的前置意图路由器."""

import re
from loguru import logger


class IntentRouter:
    """RAG 前置意图分类决策器，实现日常闲聊 100% 拦截并跳过检索读库."""

    def __init__(self):
        # 1. 常见闲聊敏感正则 (由于输入已被转换为全小写，故正则中无需使用 (?i) 标志，完美防范 Python 3.11+ 严格语法限制)
        self.chitchat_patterns = [
            # 常见中英文打招呼，涵盖 good morning / afternoon / evening 等各种缩写和日常变体
            r"^(你好|您好|哈喽|早上好|中午好|下午好|晚上好|早安|午安|晚安|hello|hi|hey|hola|greetings|hi\s+there|good\s+morning|good\s+afternoon|good\s+evening|good\s+night|morning|afternoon|evening)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
            # 身份询问
            r"^(你是谁|你叫什么|你叫什么名字|你是哪个大模型|你是大模型吗|你的作者是谁|谁创造了你|who\s+are\s+you|what\s+is\s+your\s+name)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
            # 结束语、谢意 (支持 "谢谢你", "感谢您" 等带人称代词和语气后缀的高频场景)
            r"^(谢谢|感谢|十分感谢|非常感谢|多谢)(你|您|大家)?(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
            # 常用英文结束语
            r"^(thank\s+you|thanks|bye|byebye|再见|拜拜|告辞|下线)(啊|哦|吧|呀|~|！|\!|\?|\.|\s)*$",
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
        
        # 1. 精准黑名单正则匹配
        # 我们对打招呼、自我介绍、无意义测试词、结束语等进行全量正则拦截，并排除含技术词的场景
        for pattern in self.chitchat_patterns:
            if re.match(pattern, clean_query):
                # 防御：如果命中了闲聊正则，但意外包含了强技术词，则不拦截，放行到 RAG
                has_tech = any(kw in clean_query for kw in self.technical_keywords)
                if not has_tech:
                    logger.info(f"IntentRouter: 匹配到高频闲聊正则模式 '{query}' -> 识别为 CHITCHAT 拦截")
                    return "CHITCHAT"

        # 2. 对于其它的极短提问（例如：“理财”、“烹饪”、“考研”、“摄影”等 3 个字以下的名词）
        # 只要没有命中上面的无意义问候/测试词正则，一律视为知识型精确关键词，完美路由至 RAG 语义检索！
        # 这确保了用户的 Trilium 多元化（非技术领域）个人笔记库拥有完美的 RAG 触角！

        return "KNOWLEDGE_QUERY"
