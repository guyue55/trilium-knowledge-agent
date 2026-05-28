# -*- coding: utf-8 -*-
"""测试编码修复的脚本."""

import os
import sys

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_config
from app.core.trilium_integration import TriliumService


def test_encoding_fix():
    """测试编码修复效果."""
    print("测试编码修复...")

    config = get_config()
    config.depth = 3  # 减少深度以快速测试
    config.limit = 100

    try:
        trilium_service = TriliumService(config)

        if trilium_service.client:
            print("已连接到Trilium ETAPI")

            # 获取根笔记的子笔记数量
            try:
                tree_data = trilium_service.client.traverse_note_tree(noteId="root", depth=5, limit=10000)

                if tree_data:
                    print(f"获取到 {len(tree_data)} 个笔记项")

                    # 只处理前10个进行测试
                    test_count = min(10, len(tree_data))
                    success_count = 0
                    skip_count = 0

                    for i, item in enumerate(tree_data[:test_count]):
                        if isinstance(item, dict) and "noteId" in item:
                            note_id = item["noteId"]
                            try:
                                note = trilium_service.client.get_note(note_id)
                                if note and isinstance(note, dict):
                                    title = note.get("title", "无标题")
                                    note_type = note.get("type", "text")
                                    mime = note.get("mime", "")

                                    print(f"{i + 1}. {title} (类型: {note_type}, MIME: {mime})")

                                    # 尝试获取内容
                                    try:
                                        content = trilium_service.client.get_note_content(note_id)
                                        if content:
                                            if isinstance(content, str):
                                                content_len = len(content)
                                            elif isinstance(content, bytes):
                                                content_len = len(content)
                                            else:
                                                content_len = len(str(content))
                                            print(f"   ✓ 内容长度: {content_len}")
                                            success_count += 1
                                        else:
                                            print("   ⚠ 无内容")
                                            skip_count += 1
                                    except Exception as e:
                                        print(f"   ❌ 获取内容失败: {e}")
                                        skip_count += 1
                                else:
                                    print(f"{i + 1}. 获取笔记信息失败")
                                    skip_count += 1

                            except Exception as e:
                                print(f"{i + 1}. 处理笔记 {note_id} 时出错: {e}")
                                skip_count += 1

                    print("\n测试结果:")
                    print(f"成功: {success_count}")
                    print(f"跳过: {skip_count}")
                    print(f"总计: {test_count}")

                else:
                    print("没有获取到任何笔记")

            except Exception as e:
                print(f"遍历笔记树时出错: {e}")

        else:
            print("无法连接到Trilium")

    except Exception as e:
        print(f"初始化服务时出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_encoding_fix()
