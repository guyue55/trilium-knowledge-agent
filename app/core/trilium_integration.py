# -*- coding: utf-8 -*-
"""Trilium Notes集成服务."""

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
        self.depth = 5
        self.limit = 500
        
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
                # 使用 traverse_note_tree 获取笔记树，增加limit以获取更多笔记
                tree_data = self.client.traverse_note_tree(noteId=note_id, depth=self.depth, limit=self.limit)
                if tree_data:
                    print(f"从笔记 {note_id} 遍历到 {len(tree_data)} 个笔记项")
                    # 处理遍历结果
                    processed_count = 0
                    skipped_count = 0
                    error_count = 0
                    
                    for i, item in enumerate(tree_data):
                        if isinstance(item, dict) and 'noteId' in item:
                            # 检查是否已添加过该笔记
                            if any(doc.get('note_id') == item['noteId'] for doc in documents):
                                continue
                                
                            # 获取笔记详细信息
                            try:
                                print(f"正在处理第 {i+1} 个笔记项，ID: {item['noteId']}")
                                note_detail = self.client.get_note(item['noteId'])
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
                                    
                                    title = note.get('title', 'Untitled')
                                    print(f"笔记标题: {title}")
                                    
                                    # 获取笔记内容
                                    content = ""
                                    try:
                                        content_response = self.client.get_note_content(item['noteId'])
                                        if content_response and isinstance(content_response, str):
                                            content = content_response
                                            print(f"通过 get_note_content 成功获取笔记 {item['noteId']} 内容，长度: {len(content)}")
                                    except Exception as e:
                                        print(f"获取笔记 {item['noteId']} 内容时出错: {e}")
                                        # 继续尝试其他方法
                                    
                                    # 如果通过 get_note_content 获取不到内容，则尝试从 note 对象获取
                                    if not content:
                                        content = note.get('content', '')
                                        if content:
                                            print(f"通过 note 对象获取笔记 {item['noteId']} 内容，长度: {len(content)}")
                                    
                                    print(f"最终获取到的内容长度: {len(content) if content else 0}")
                                    
                                    # 只有当内容不为空且不是字典时才添加到文档列表
                                    if content and not isinstance(content, dict) and isinstance(content, str) and content.strip():
                                        documents.append({
                                            'content': content,
                                            'title': title if title else f"笔记 {item['noteId']}",
                                            'note_id': item['noteId'],
                                            'attributes': []
                                        })
                                        print(f"成功添加笔记: {title} ({item['noteId']})")
                                        processed_count += 1
                                        
                                        # 增加文档数量限制以处理更多文档
                                        if len(documents) >= 500:
                                            print("达到文档数量上限 (500)")
                                            return
                                    elif content and isinstance(content, str):
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
            if content_response and isinstance(content_response, str):
                return content_response
                
            # 如果上面的方法失败，尝试通过 get_note 获取
            response = self.client.get_note(note_id)
            if response and isinstance(response, dict):
                if 'note' in response and 'content' in response['note']:
                    return response['note']['content']
                elif 'content' in response:
                    return response['content']
        except Exception as e:
            print(f"获取笔记内容时出错: {e}")
            
        return ""
    
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