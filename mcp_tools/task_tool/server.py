#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Task 工具 MCP 服务器
符合 MCP 协议标准
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class TaskServer:
    """Task 工具服务器"""
    
    def __init__(self, data_dir: Path):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.tasks_file = data_dir / 'tasks.json'
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """确保数据文件存在"""
        if not self.tasks_file.exists():
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_tasks(self) -> List[Dict[str, Any]]:
        """加载所有任务"""
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_tasks(self, tasks: List[Dict[str, Any]]):
        """保存任务"""
        with open(self.tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    def _find_task(self, task_id: str) -> tuple:
        """查找任务，返回 (任务, 索引)"""
        tasks = self._load_tasks()
        for i, task in enumerate(tasks):
            if task.get("id") == task_id:
                return task, i
        return None, -1
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "tasks.log":
            return self._log_task(arguments)
        elif tool_name == "tasks.status":
            return self._update_status(arguments)
        elif tool_name == "tasks.finish":
            return self._finish_task(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _log_task(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """记录任务日志"""
        tasks = self._load_tasks()
        
        task_id = arguments.get("task_id")
        message = arguments.get("message", "")
        
        if not task_id or not message:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: task_id 和 message"
            }
        
        task, index = self._find_task(task_id)
        if not task:
            # 如果任务不存在，创建新任务
            task = {
                "id": task_id,
                "status": "created",
                "logs": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            tasks.append(task)
            index = len(tasks) - 1
        
        # 添加日志
        log_entry = {
            "id": str(uuid.uuid4()),
            "message": message,
            "level": arguments.get("level", "info"),
            "data": arguments.get("data", {}),
            "timestamp": datetime.now().isoformat()
        }
        
        if "logs" not in task:
            task["logs"] = []
        task["logs"].append(log_entry)
        task["updated_at"] = datetime.now().isoformat()
        
        tasks[index] = task
        self._save_tasks(tasks)
        
        return {
            "success": True,
            "content": {
                "id": log_entry["id"],
                "task_id": task_id,
                "logged_at": log_entry["timestamp"]
            },
            "error": None
        }
    
    def _update_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """更新任务状态"""
        tasks = self._load_tasks()
        
        task_id = arguments.get("task_id")
        status = arguments.get("status")
        
        if not task_id or not status:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: task_id 和 status"
            }
        
        task, index = self._find_task(task_id)
        if not task:
            return {
                "success": False,
                "content": None,
                "error": f"任务不存在: {task_id}"
            }
        
        # 更新状态
        task["status"] = status
        if "progress" in arguments:
            task["progress"] = arguments["progress"]
        if "message" in arguments:
            task["status_message"] = arguments["message"]
        task["updated_at"] = datetime.now().isoformat()
        
        tasks[index] = task
        self._save_tasks(tasks)
        
        return {
            "success": True,
            "content": task,
            "error": None
        }
    
    def _finish_task(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """标记任务完成"""
        tasks = self._load_tasks()
        
        task_id = arguments.get("task_id")
        if not task_id:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: task_id"
            }
        
        task, index = self._find_task(task_id)
        if not task:
            return {
                "success": False,
                "content": None,
                "error": f"任务不存在: {task_id}"
            }
        
        # 标记完成
        task["status"] = "completed"
        task["progress"] = 100
        if "result" in arguments:
            task["result"] = arguments["result"]
        if "summary" in arguments:
            task["summary"] = arguments["summary"]
        task["completed_at"] = datetime.now().isoformat()
        task["updated_at"] = datetime.now().isoformat()
        
        tasks[index] = task
        self._save_tasks(tasks)
        
        return {
            "success": True,
            "content": task,
            "error": None
        }


def create_server(data_dir: str = None) -> TaskServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        TaskServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'task_tool'
    
    data_path.mkdir(parents=True, exist_ok=True)
    
    return TaskServer(data_path)

