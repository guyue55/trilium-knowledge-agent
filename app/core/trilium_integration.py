# -*- coding: utf-8 -*-
"""Trilium Notes集成服务."""
import json

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.core.config import Config
from typing import List, Dict, Any, Optional
from trilium_py.client import ETAPI
import os


class TriliumService:
    """用于集成Trilium Notes的服务."""
    
    def __init__(self, config: Config) -> None:
        """初始化Trilium服务.
        
        Args:
            config: 应用程序配置对象.
        """
        self.base_url = config.trilium_base_url or ""
        self.token = config.trilium_token or ""
        self.note_ids = config.note_ids or ['root']
        self.data_dir = config.trilium_data_dir or "."
        # 设置遍历参数
        self.depth = config.depth or 5
        self.limit = config.limit or 500
        
        # 初始化Trilium客户端
        if self.base_url and self.token:
            try:
                self.client = ETAPI(server_url=self.base_url, token=self.token)
                print("Trilium客户端初始化成功")
                # 测试连接
                try:
                    test_result = self.client.get_note('root')
                    if test_result and isinstance(test_result, dict) and 'status' not in test_result:
                        print("Trilium连接测试成功")
                    else:
                        print(f"Trilium连接测试失败: {test_result}")
                except Exception as e:
                    print(f"Trilium连接测试失败: {e}")
            except Exception as e:
                print(f"Trilium客户端初始化失败: {e}")
                self.client = None
        else:
            self.client = None
            print("Trilium配置不完整，部分功能可能不可用")
        
        # 设置文件系统监控
        try:
            self.event_handler = TriliumChangeHandler(self)
            self.observer = Observer()
            self.observer.schedule(
                self.event_handler,
                path=self.data_dir,
                recursive=True
            )
            self.observer.start()
        except Exception as e:
            print(f"文件系统监控初始化失败: {e}")
    
    def load_documents(self) -> List[Dict[str, Any]]:
        """从Trilium加载文档.
        
        Returns:
            从Trilium加载的文档列表.
        """
        documents = []
        
        # 如果Trilium客户端可用，尝试加载真实文档
        if self.client:
            try:
                # 尝试获取一些真实内容
                self._try_load_real_documents(documents)
                print(f"尝试加载文档后，documents 数量: {len(documents)}")
                if documents:
                    print(f"成功从Trilium加载 {len(documents)} 个真实文档")
                    return documents
                else:
                    print("没有成功加载任何真实文档")
            except Exception as e:
                print(f"加载真实Trilium文档时出错: {e}")
                import traceback
                traceback.print_exc()
        
        # 只有在没有成功加载真实文档时才使用示例文档
        print("加载Trilium文档（使用示例内容）...")
        
        # 添加一些示例文档
        sample_docs = [
            {
                'content': '你好，这是一个测试文档。',
                'title': '测试文档1',
                'note_id': 'test1',
                'attributes': []
            },
            {
                'content': '欢迎使用Trilium知识库智能助手。',
                'title': '欢迎使用',
                'note_id': 'test2',
                'attributes': []
            },
            {
                'content': '这是第二篇测试文档，包含更多内容，用于测试知识库问答功能。',
                'title': '测试文档2',
                'note_id': 'test3',
                'attributes': []
            }
        ]
        
        documents.extend(sample_docs)
        print(f"已加载 {len(sample_docs)} 个示例文档")
        
        return documents

    def collect_all_paths(self, tree: dict, parent_path: str = "") -> list[dict]:
        """
        从树结构中递归收集所有笔记的完整路径

        :param tree: traverse_note_tree 返回的嵌套字典
        :param parent_path: 父级路径（递归传递）
        :return: 包含 note_id, title, path 的字典列表
        """
        results = []

        # 提取当前节点信息
        note_id = tree.get("noteId")
        title = tree.get("title", "untitled")

        # 构建当前节点的完整路径
        current_path = f"{parent_path}/{note_id}" if parent_path else note_id

        # 存储当前节点信息
        results.append({
            "noteId": note_id,
            "title": title,
            "path": current_path
        })

        print(f"正在处理笔记 {note_id}")
        print(tree)
        note_detail = self.client.get_note(note_id)
        content_response = self.client.get_note_content(note_id)

        # 递归处理子节点
        for child in tree.get("children", []):
            # 将当前路径传递给子节点作为父路径
            results.extend(self.collect_all_paths(child, current_path))

        return results
    
    def _try_load_real_documents(self, documents: List[Dict[str, Any]], ) -> None:
        """尝试加载真实的Trilium文档.
        
        Args:
            documents: 文档列表
        """
        if not self.client:
            return
            
        try:
            # 使用配置中指定的note_ids或者默认使用'root'
            note_ids_to_process = self.note_ids
            print(f"准备从以下笔记ID加载文档: {note_ids_to_process}")
            
            for note_id in note_ids_to_process:
                print(f"遍历设置({note_id})： 深度 {self.depth}，限制 {self.limit}")
                # 使用 traverse_note_tree 获取笔记树，增加limit以获取更多笔记
                tree_data = self.client.traverse_note_tree(noteId=note_id, depth=5, limit=100)
                if tree_data:
                    print(f"从笔记 {note_id} 遍历到 {len(tree_data)} 个笔记项")
                    # 处理遍历结果
                    processed_count = 0
                    skipped_count = 0
                    error_count = 0

                    for i, item in enumerate(tree_data):
                        print(f"i: {i}")
                        # print(f"item: {json.dumps(item, ensure_ascii=False)}")
                        _id = item['noteId']
                        title = item.get('title', 'Untitled')
                        content = self._process_content(item.get('content', ''), _id)

                        print(f"笔记标题: {title}")
                        print(f"笔记内容: {content}")
                        # # 2. 收集所有路径（纯内存操作，无额外请求）
                        # all_paths = self.collect_all_paths(item)
                        #
                        # # 3. 打印结果
                        # for item in all_paths:
                        #     print(f"标题: {item['title']}")
                        #     print(f"完整路径: {item['path']}")
                        #     print(f"Note ID: {item['noteId']}")
                        #     print("-" * 40)
                        #
                        # import time
                        # time.sleep(9000)

                        if isinstance(item, dict) and 'noteId' in item:
                            # 检查是否已添加过该笔记
                            if any(doc.get('note_id') == item['noteId'] for doc in documents):
                                continue

                            # 获取笔记详细信息
                            try:
                                print(f"正在处理第 {i+1} 个笔记项，ID: {item['noteId']}")
                                # note_detail = self.client.get_note(item['noteId'])
                                note_detail = item
                                print(f"获取笔记详情结果类型: {type(note_detail)}")
                                
                                # 检查返回的数据格式
                                if note_detail and isinstance(note_detail, dict):
                                    # 新的API格式直接返回笔记信息，而不是包装在'note'键中
                                    if 'noteId' in note_detail:
                                        note = note_detail
                                    elif 'note' in note_detail:
                                        # 兼容旧格式
                                        note = note_detail['note']
                                    else:
                                        print(f"笔记详情格式不符合预期: {note_detail}")
                                        error_count += 1
                                        continue
                                    
                                    # title = note.get('title', 'Untitled')
                                    # content = self._process_content(note.get('content', ''), note)

                                    # print(f"笔记标题: {title}")
                                    # print(f"笔记内容: {content}")
                                    
                                    # 检查笔记类型，跳过非文本类型的笔记
                                    note_type = note.get('type', 'text')
                                    mime = note.get('mime', '')
                                    
                                    # 跳过明显的二进制文件类型
                                    binary_types = ['file', 'image', 'application/pdf', 'application/zip', 'application/octet-stream']
                                    if note_type not in ['text', 'code', 'render'] or mime in binary_types:
                                        print(f"跳过非文本类型笔记 {item['noteId']} , title: {title} (类型: {note_type}, MIME: {mime})")
                                        skipped_count += 1
                                        continue
                                    
                                    # 打印完整的笔记信息以查看所有字段
                                    # print("笔记完整信息字段:")
                                    # for key in sorted(note.keys()):
                                    #     value = note[key]
                                    #     if key not in ['content']:  # 避免打印过长的内容
                                    #         print(f"  {key}: {value}")
                                    
                                    # 尝试获取笔记的路径信息
                                    # note_path = self.get_note_path(item['noteId'])
                                    note_path = ""
                                    print(f"笔记 {item['noteId']} 的路径: {note_path}")
                                    
                                    # # 获取笔记内容
                                    # try:
                                    #     content_response = self.client.get_note_content(item['noteId'])
                                    #     if content_response and isinstance(content_response, str):
                                    #         content = content_response
                                    #         print(f"通过 get_note_content 成功获取笔记 {item['noteId']} 内容，长度: {len(content)}")
                                    #         print(content)
                                    #     elif content_response:
                                    #         # 尝试处理可能的二进制内容
                                    #         try:
                                    #             content = str(content_response, 'utf-8')
                                    #         except (UnicodeDecodeError, TypeError):
                                    #             # 如果无法解码为UTF-8，则可能是二进制内容，跳过
                                    #             print(f"笔记 {item['noteId']} 包含二进制内容，跳过处理")
                                    #             content = ""
                                    # except Exception as e:
                                    #     print(f"获取笔记 {item['noteId']} 内容时出错: {e}")
                                    #     # 继续尝试其他方法
                                    #
                                    # # 如果通过 get_note_content 获取不到内容，则尝试从 note 对象获取
                                    # if not content:
                                    #     note_content = note.get('content', '')
                                    #     if note_content:
                                    #         # 处理可能的二进制内容
                                    #         processed_content = self._process_content(note_content, item['noteId'])
                                    #         if processed_content is not None:
                                    #             content = processed_content
                                    #             print(f"通过 note 对象获取笔记 {item['noteId']} 内容，长度: {len(content)}")
                                    
                                    print(f"最终获取到的内容长度: {len(content) if content else 0}")
                                    
                                    # 只有当内容不为空且不是字典时才添加到文档列表
                                    if content and not isinstance(content, dict) and isinstance(content, str) and content.strip():
                                        documents.append({
                                            'content': content,
                                            'title': title if title else f"笔记 {item['noteId']}",
                                            'note_id': item['noteId'],
                                            'attributes': [],
                                            'path': note_path  # 添加路径信息
                                        })
                                        print(f"成功添加笔记: {title} ({item['noteId']})，路径: {note_path}")
                                        processed_count += 1
                                        
                                        # 增加文档数量限制以处理更多文档
                                        if len(documents) >= self.limit:
                                            print(f"达到文档数量上限 ({self.limit})")
                                            return
                                    elif content is not None and isinstance(content, str):
                                        print(f"跳过空内容笔记: {title} ({item['noteId']})")
                                        skipped_count += 1
                                    else:
                                        print(f"完全无法获取内容: {title} ({item['noteId']})")
                                        skipped_count += 1
                                else:
                                    print(f"笔记详情格式不符合预期: {note_detail}")
                                    error_count += 1
                            except Exception as e:
                                print(f"处理笔记 {item['noteId']} 时出错: {e}")
                                error_count += 1
                                continue
                    
                    print(f"处理统计 - 成功: {processed_count}, 跳过: {skipped_count}, 错误: {error_count}")
                    # 如果我们至少处理了一个真实文档，则不需要使用示例文档
                    if processed_count > 0:
                        print(f"成功处理了 {processed_count} 个真实文档")

                        import time
                        time.sleep(100)
                        return
                        
        except Exception as e:
            print(f"尝试加载真实文档时出错: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_note_content(self, note_id: str) -> str:
        """获取特定笔记的内容.
        
        Args:
            note_id: 要检索的笔记ID.
            
        Returns:
            指定笔记的内容.
        """
        if not self.client:
            return ""
            
        try:
            # 优先尝试通过 get_note_content 获取内容
            content_response = self.client.get_note_content(note_id)
            content = self._process_content(content_response, note_id)
            if content is not None:
                return content
                
            # 如果上面的方法失败，尝试通过 get_note 获取
            response = self.client.get_note(note_id)
            if response and isinstance(response, dict):
                if 'note' in response and 'content' in response['note']:
                    content = self._process_content(response['note']['content'], note_id)
                elif 'content' in response:
                    content = self._process_content(response['content'], note_id)
                else:
                    content = ""
                if content is not None:
                    return content
        except Exception as e:
            print(f"获取笔记内容时出错: {e}")
            
        return ""
    
    def _process_content(self, content, note_id: str) -> str:
        """处理笔记内容，确保它是有效的文本.
        
        Args:
            content: 原始内容
            note_id: 笔记ID（用于日志）
            
        Returns:
            处理后的内容，如果是二进制内容则返回None
        """
        if not content:
            return ""
            
        if isinstance(content, str):
            # 检查是否是有效的文本内容
            if len(content) > 0:
                # 解码HTML实体编码
                try:
                    from html import unescape
                    decoded_content = unescape(content)
                    return decoded_content
                except Exception as e:
                    print(f"解码HTML实体时出错: {e}")
                    return content
            else:
                return ""
        else:
            # 尝试处理可能的二进制内容
            try:
                # 如果是bytes类型
                if isinstance(content, bytes):
                    # 检查是否可能是文本内容
                    try:
                        # 尝试解码为UTF-8
                        decoded_content = content.decode('utf-8')
                        # 解码HTML实体编码
                        try:
                            from html import unescape
                            decoded_content = unescape(decoded_content)
                        except Exception as e:
                            print(f"解码HTML实体时出错: {e}")
                        # 检查解码后的内容是否合理（不包含太多控制字符）
                        control_chars = sum(1 for c in decoded_content if ord(c) < 32 and c not in '\n\r\t')
                        if control_chars / len(decoded_content) > 0.1 if len(decoded_content) > 0 else 0:
                            print(f"笔记 {note_id} 包含过多控制字符，可能是二进制内容")
                            return None
                        return decoded_content
                    except UnicodeDecodeError:
                        print(f"笔记 {note_id} 无法解码为UTF-8，可能是二进制内容")
                        return None
                
                # 其他类型尝试转换为字符串
                decoded_content = str(content, 'utf-8')
                # 解码HTML实体编码
                try:
                    from html import unescape
                    decoded_content = unescape(decoded_content)
                except Exception as e:
                    print(f"解码HTML实体时出错: {e}")
                return decoded_content
            except (UnicodeDecodeError, TypeError):
                # 如果无法解码为UTF-8，则可能是二进制内容
                print(f"笔记 {note_id} 包含二进制内容，无法处理为文本")
                return None
    
    def get_note_path(self, note_id: str) -> str:
        """获取笔记的完整路径.
        
        Args:
            note_id: 要获取路径的笔记ID.
            
        Returns:
            笔记的完整路径字符串.
        """
        if not self.client:
            return ""
            
        try:
            # 首先尝试使用 search_note 方法获取笔记信息
            search_result = self.client.search_note(note_id)
            print(f"搜索笔记 {note_id} 的结果: {search_result}")

            # import json
            # with open("result.json", "w") as f:
            #     json.dump(search_result, f, indent=4)

            # 然后尝试直接从笔记信息中获取路径
            note_detail = self.client.get_note(note_id)
            print(f"笔记 {note_id} 的详细信息: {note_detail}")
            if note_detail and isinstance(note_detail, dict):
                # 检查是否有路径信息字段
                path_fields = ['path', 'paths', 'notePath', 'parents', 'parentNoteIds']
                found_path_field = None
                for field in path_fields:
                    if field in note_detail and note_detail[field]:
                        found_path_field = field
                        print(f"找到路径字段 {field}: {note_detail[field]} (类型: {type(note_detail[field])})")
                        break
                
                if found_path_field:
                    # 根据不同字段类型处理路径
                    path_data = note_detail[found_path_field]
                    if isinstance(path_data, list):
                        if len(path_data) > 0:
                            if isinstance(path_data[0], dict) and 'noteId' in path_data[0]:
                                # 路径是由字典组成的列表
                                path_parts = [item['noteId'] for item in path_data if 'noteId' in item]
                                path_str = '/'.join(path_parts)
                                print(f"从字典列表构建的路径: {path_str}")
                                return path_str
                            elif isinstance(path_data[0], str):
                                # 路径是字符串列表
                                path_str = '/'.join(path_data)
                                print(f"从字符串列表构建的路径: {path_str}")
                                return path_str
                    elif isinstance(path_data, str):
                        # 路径已经是字符串格式
                        print(f"直接使用路径字符串: {path_data}")
                        return path_data
            
            # 如果直接获取不到路径信息，则尝试通过遍历树形结构查找
            print(f"尝试通过遍历树形结构查找笔记 {note_id} 的路径")
            tree_data = self.client.traverse_note_tree(noteId='root', depth=self.depth, limit=self.limit)
            if tree_data and isinstance(tree_data, list):
                # 在树形结构中查找指定的笔记
                path = self._find_note_path(tree_data, note_id, [])
                if path:
                    # 构建路径字符串，跳过root节点
                    if len(path) > 1:
                        path_str = '/'.join(path[1:])  # 跳过root
                        print(f"通过遍历找到笔记 {note_id} 的路径: {path_str}")
                        return path_str
                    else:
                        print(f"路径太短: {path}")
        except Exception as e:
            print(f"获取笔记路径时出错: {e}")
            import traceback
            traceback.print_exc()
            
        return ""
    
    def _find_note_path(self, tree_data: list, target_note_id: str, current_path: list) -> list:
        """在树形结构中递归查找笔记路径.
        
        Args:
            tree_data: 树形结构数据.
            target_note_id: 目标笔记ID.
            current_path: 当前路径.
            
        Returns:
            笔记的路径列表.
        """
        for item in tree_data:
            if isinstance(item, dict):
                if item.get('noteId') == target_note_id:
                    # 找到目标笔记，返回路径
                    return current_path + [target_note_id]
                
                # 递归查找子节点
                if 'children' in item and item['children']:
                    result = self._find_note_path(
                        item['children'], 
                        target_note_id, 
                        current_path + [item['noteId']]
                    )
                    if result:
                        return result
        
        return []
    
    def update_knowledge_base(self) -> None:
        """当Trilium笔记更改时更新知识库."""
        # 触发知识库更新处理
        print("正在更新知识库...")


class TriliumChangeHandler(FileSystemEventHandler):
    """Trilium文件系统事件的处理程序."""
    
    def __init__(self, service: TriliumService) -> None:
        """初始化变更处理器.
        
        Args:
            service: 要通知变更的Trilium服务.
        """
        self.service = service
    
    def on_modified(self, event) -> None:
        """处理文件修改事件.
        
        Args:
            event: 文件系统事件.
        """
        if "notes" in event.src_path:
            print(f"检测到知识库更新: {event.src_path}")
            # 触发知识库更新处理
            self.service.update_knowledge_base()