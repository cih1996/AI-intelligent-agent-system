#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory 工具 MCP 服务器
符合 MCP 协议标准
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class MemoryServer:
    """Memory 工具服务器"""
    
    def __init__(self, data_dir: Path):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.memory_file = data_dir / 'memory.json'
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """确保数据文件存在"""
        if not self.memory_file.exists():
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_memories(self) -> List[Dict[str, Any]]:
        """加载所有记忆"""
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_memories(self, memories: List[Dict[str, Any]]):
        """保存记忆"""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "memory.write":
            return self._write_memory(arguments)
        elif tool_name == "memory.load":
            return self._load_memory(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _write_memory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """写入记忆"""
        memories = self._load_memories()
        
        content = arguments.get("content", "")
        if not content:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: content"
            }
        
        memory_id = str(uuid.uuid4())
        memory_type = arguments.get("type", "short_term")
        
        new_memory = {
            "id": memory_id,
            "content": content,
            "type": memory_type,
            "context": arguments.get("context", ""),
            "tags": arguments.get("tags", []),
            "importance": arguments.get("importance", 5),
            "created_at": datetime.now().isoformat()
        }
        
        memories.append(new_memory)
        self._save_memories(memories)
        
        return {
            "success": True,
            "content": {
                "id": memory_id,
                "type": memory_type,
                "written_at": new_memory["created_at"]
            },
            "error": None
        }
    
    def _load_memory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆"""
        memories = self._load_memories()
        
        # 类型过滤
        type_filter = arguments.get("type", "all")
        if type_filter != "all":
            memories = [m for m in memories if m.get("type") == type_filter]
        
        # 重要性过滤
        importance_min = arguments.get("importance_min")
        if importance_min:
            memories = [m for m in memories if m.get("importance", 0) >= importance_min]
        
        # 查询搜索
        query = arguments.get("query", "").lower()
        if query:
            filtered = []
            for m in memories:
                content = m.get("content", "").lower()
                context = m.get("context", "").lower()
                if query in content or query in context:
                    filtered.append(m)
            memories = filtered
        
        # 按重要性排序
        memories.sort(key=lambda x: x.get("importance", 0), reverse=True)
        
        # 应用限制
        limit = arguments.get("limit")
        if limit:
            memories = memories[:limit]
        
        return {
            "success": True,
            "content": {
                "memories": memories,
                "total": len(self._load_memories()),
                "matched": len(memories)
            },
            "error": None
        }


def create_server(data_dir: str = None) -> MemoryServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        MemoryServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'memory_tool'
    
    data_path.mkdir(parents=True, exist_ok=True)
    
    return MemoryServer(data_path)

