# -*- coding: utf-8 -*-
"""最小化测试Chroma."""

try:
    from langchain_community.vectorstores import Chroma
    print("✓ 成功导入 Chroma")
    
    # 直接测试Chroma，不使用嵌入模型
    vector_store = Chroma(persist_directory="./test_chroma_db")
    print("✓ 成功创建 Chroma 向量存储（无嵌入模型）")
    
    # 清理测试数据
    import shutil
    import os
    if os.path.exists("./test_chroma_db"):
        shutil.rmtree("./test_chroma_db")
    print("✓ 测试完成，清理临时数据")
    
except Exception as e:
    print(f"✗ 创建 Chroma 时出错: {e}")
    import traceback
    traceback.print_exc()