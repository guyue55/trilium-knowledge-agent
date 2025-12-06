# -*- coding: utf-8 -*-
"""下载Qwen模型的脚本."""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import get_config

def download_qwen_model():
    """下载Qwen/Qwen1.5-1.8B-Chat模型."""
    try:
        from huggingface_hub import snapshot_download
        config = get_config()
        
        # 设置镜像源
        if config.hf_endpoint:
            os.environ['HF_ENDPOINT'] = config.hf_endpoint
            print(f"使用镜像源: {config.hf_endpoint}")
        
        # 创建模型目录
        model_path = Path(config.llm_model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        # 如果模型已存在，跳过下载
        if model_path.exists():
            print(f"模型文件已存在: {model_path}")
            return True
        
        print("开始下载Qwen/Qwen1.5-1.8B-Chat模型...")
        print(f"保存到: {model_path}")
        
        # 下载模型
        snapshot_download(
            repo_id="Qwen/Qwen1.5-1.8B-Chat",
            local_dir=str(model_path),
            local_dir_use_symlinks=False
        )
        print("Qwen/Qwen1.5-1.8B-Chat模型下载完成!")
        
    except Exception as e:
        print(f"下载Qwen/Qwen1.5-1.8B-Chat模型时出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """主函数."""
    print("开始下载Qwen模型...")
    
    if not download_qwen_model():
        print("Qwen模型下载失败!")
        return False
    
    print("Qwen模型下载完成!")
    return True

if __name__ == "__main__":
    main()