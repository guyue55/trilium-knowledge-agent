# -*- coding: utf-8 -*-
"""用于安全更新知识库的脚本，处理中断和错误."""

import sys
import os
import signal
import time

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_config
from app.core.trilium_integration import TriliumService

# 全局变量用于处理中断
interrupted = False

def signal_handler(signum, frame):
    """处理中断信号."""
    global interrupted
    print("\n收到中断信号，正在安全退出...")
    interrupted = True

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def update_knowledge_base_safe():
    """使用来自Trilium的最新文档更新知识库，处理中断."""
    print("正在安全更新知识库...")
    
    # 获取配置
    config = get_config()
    
    # 设置全量更新的限制
    # 由于已修复编码和二进制文件问题，现在可以安全地增加限制
    config.depth = int(os.getenv("TRILIUM_SAFE_DEPTH", 20))
    config.limit = int(os.getenv("TRILIUM_SAFE_LIMIT", 20000))
    
    # 强制使用高限制以满足用户全量更新的需求
            
    print(f"已设置文档获取限制为: {config.limit}, 深度: {config.depth}")
    
    try:
        # 初始化服务
        trilium_service = TriliumService(config)
        
        # 从Trilium加载文档
        print("正在从Trilium加载文档...")
        
        # 检查是否有可用的Trilium客户端
        if trilium_service.client:
            print("已连接到Trilium ETAPI")
            
            # 手动调用加载方法以获取详细日志
            documents = []
            try:
                trilium_service._try_load_real_documents(documents)
                print(f"成功从Trilium加载 {len(documents)} 个文档")
                
                # 显示前几个文档的信息
                if documents:
                    for i, doc in enumerate(documents[:5]):
                        print(f"文档 {i+1}: {doc.get('title', '无标题')} (长度: {len(doc.get('content', ''))})")
                
                if len(documents) > 5:
                    print(f"... 还有 {len(documents) - 5} 个文档")
                    
                print(f"总计成功加载: {len(documents)} 个文档")
                return len(documents)
                
            except KeyboardInterrupt:
                print("\n用户中断操作")
                return len(documents) if 'documents' in locals() else 0
            except Exception as e:
                print(f"加载文档时出错: {e}")
                import traceback
                traceback.print_exc()
                return 0
        else:
            print("无法连接到Trilium，将使用示例数据")
            documents = trilium_service.load_documents()
            print(f"使用示例数据: {len(documents)} 个文档")
            return len(documents)
            
    except Exception as e:
        print(f"更新知识库时出错: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    try:
        doc_count = update_knowledge_base_safe()
        print(f"\n操作完成，共处理 {doc_count} 个文档")
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"发生错误: {e}")
