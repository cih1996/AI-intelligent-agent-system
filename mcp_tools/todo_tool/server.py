#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Todo 工具 MCP 服务器
符合 MCP 协议标准
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class TodoServer:
    """Todo 工具服务器"""
    
    def __init__(self, data_dir: Path):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.todo_file = data_dir / 'todos.json'
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """确保数据文件存在"""
        if not self.todo_file.exists():
            with open(self.todo_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_todos(self) -> List[Dict[str, Any]]:
        """加载所有待办事项"""
        try:
            with open(self.todo_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_todos(self, todos: List[Dict[str, Any]]):
        """保存待办事项"""
        with open(self.todo_file, 'w', encoding='utf-8') as f:
            json.dump(todos, f, ensure_ascii=False, indent=2)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "todo.add":
            return self._add_todo(arguments)
        elif tool_name == "todo.update":
            return self._update_todo(arguments)
        elif tool_name == "todo.list":
            return self._list_todos(arguments)
        elif tool_name == "todo.remove":
            return self._remove_todo(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _add_todo(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """添加待办事项"""
        todos = self._load_todos()
        
        todo_id = str(uuid.uuid4())
        new_todo = {
            "id": todo_id,
            "title": arguments.get("title", ""),
            "details": arguments.get("details", ""),
            "priority": arguments.get("priority", "medium"),
            "status": "pending",
            "due_date": arguments.get("due_date"),
            "tags": arguments.get("tags", []),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        todos.append(new_todo)
        self._save_todos(todos)
        
        return {
            "success": True,
            "content": {
                "id": todo_id,
                "title": new_todo["title"],
                "status": new_todo["status"],
                "created_at": new_todo["created_at"]
            },
            "error": None
        }
    
    def _update_todo(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """更新待办事项"""
        todos = self._load_todos()
        todo_id = arguments.get("id")
        
        if not todo_id:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: id"
            }
        
        # 查找待办事项
        todo = None
        for t in todos:
            if t.get("id") == todo_id:
                todo = t
                break
        
        if not todo:
            return {
                "success": False,
                "content": None,
                "error": f"待办事项不存在: {todo_id}"
            }
        
        # 更新字段
        if "title" in arguments:
            todo["title"] = arguments["title"]
        if "details" in arguments:
            todo["details"] = arguments["details"]
        if "priority" in arguments:
            todo["priority"] = arguments["priority"]
        if "status" in arguments:
            todo["status"] = arguments["status"]
        if "due_date" in arguments:
            todo["due_date"] = arguments["due_date"]
        if "tags" in arguments:
            todo["tags"] = arguments["tags"]
        
        todo["updated_at"] = datetime.now().isoformat()
        self._save_todos(todos)
        
        return {
            "success": True,
            "content": todo,
            "error": None
        }
    
    def _list_todos(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """列出待办事项"""
        todos = self._load_todos()
        
        # 应用过滤器
        filtered = todos.copy()
        
        status_filter = arguments.get("status", "all")
        if status_filter != "all":
            filtered = [t for t in filtered if t.get("status") == status_filter]
        
        priority_filter = arguments.get("priority")
        if priority_filter:
            filtered = [t for t in filtered if t.get("priority") == priority_filter]
        
        tag_filter = arguments.get("tag")
        if tag_filter:
            filtered = [t for t in filtered if tag_filter in t.get("tags", [])]
        
        # 应用限制
        limit = arguments.get("limit")
        if limit:
            filtered = filtered[:limit]
        
        return {
            "success": True,
            "content": {
                "todos": filtered,
                "total": len(todos),
                "filtered": len(filtered)
            },
            "error": None
        }
    
    def _remove_todo(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """删除待办事项"""
        todos = self._load_todos()
        todo_id = arguments.get("id")
        
        if not todo_id:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: id"
            }
        
        # 查找并删除待办事项
        original_count = len(todos)
        todos = [t for t in todos if t.get("id") != todo_id]
        
        if len(todos) == original_count:
            return {
                "success": False,
                "content": None,
                "error": f"待办事项不存在: {todo_id}"
            }
        
        self._save_todos(todos)
        
        return {
            "success": True,
            "content": {
                "id": todo_id,
                "message": "待办事项已删除"
            },
            "error": None
        }


def create_server(data_dir: str = None) -> TodoServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        TodoServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'todo_tool'
    
    data_path.mkdir(parents=True, exist_ok=True)
    
    return TodoServer(data_path)

