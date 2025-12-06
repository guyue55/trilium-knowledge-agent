# -*- coding: utf-8 -*-
"""模型下载脚本，用于自动下载嵌入模型和语言模型."""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import get_config

def download_embedding_model():
    """下载嵌入模型."""
    try:
        from huggingface_hub import snapshot_download
        config = get_config()
        
        # 设置镜像源
        if config.hf_endpoint:
            os.environ['HF_ENDPOINT'] = config.hf_endpoint
            print(f"使用镜像源: {config.hf_endpoint}")
        
        # 创建模型目录
        local_path = Path(config.embedding_model_local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"开始下载嵌入模型: {config.embedding_model}")
        print(f"保存到: {local_path}")
        
        # 下载模型
        snapshot_download(
            repo_id=config.embedding_model,
            local_dir=str(local_path),
            local_dir_use_symlinks=False
        )
        print("嵌入模型下载完成!")
        
    except Exception as e:
        print(f"下载嵌入模型时出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def download_gpt4all_model():
    """下载GPT4All模型."""
    try:
        import requests
        from tqdm import tqdm
        
        config = get_config()
        model_path = Path(config.llm_model_path)
        
        # 创建模型目录
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果模型已存在，跳过下载
        if model_path.exists():
            print(f"模型文件已存在: {model_path}")
            return True
            
        # GPT4All模型下载URL (这里使用一个示例模型)
        # 实际使用时应替换为真实的模型下载地址
        model_url = "https://gpt4all.io/models/ggml-gpt4all-j-v1.3-groovy.bin"
        
        print(f"开始下载GPT4All模型...")
        print(f"URL: {model_url}")
        print(f"保存到: {model_path}")
        
        # 下载文件
        response = requests.get(model_url, stream=True)
        response.raise_for_status()
        
        # 获取文件大小
        total_size = int(response.headers.get('content-length', 0))
        
        # 保存文件并显示进度条
        with open(model_path, 'wb') as f, tqdm(
            desc=model_path.name,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))
        
        print("GPT4All模型下载完成!")
        return True
        
    except Exception as e:
        print(f"下载GPT4All模型时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数."""
    print("开始下载所需模型...")
    
    # 下载嵌入模型
    print("\n=== 下载嵌入模型 ===")
    if not download_embedding_model():
        print("嵌入模型下载失败!")
        return False
    
    # 下载GPT4All模型
    print("\n=== 下载GPT4All模型 ===")
    if not download_gpt4all_model():
        print("GPT4All模型下载失败!")
        return False
    
    print("\n所有模型下载完成!")
    return True

if __name__ == "__main__":
    main()