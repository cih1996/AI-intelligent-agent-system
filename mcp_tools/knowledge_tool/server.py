#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Knowledge 工具 MCP 服务器
符合 MCP 协议标准
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class KnowledgeServer:
    """Knowledge 工具服务器"""
    
    def __init__(self, data_dir: Path):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir
        self.knowledge_file = data_dir / 'knowledge.json'
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """确保数据文件存在"""
        if not self.knowledge_file.exists():
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_knowledge(self) -> List[Dict[str, Any]]:
        """加载所有知识条目"""
        try:
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_knowledge(self, knowledge: List[Dict[str, Any]]):
        """保存知识条目"""
        with open(self.knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "knowledge.store":
            return self._store_knowledge(arguments)
        elif tool_name == "knowledge.retrieve":
            return self._retrieve_knowledge(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _store_knowledge(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """存储知识条目"""
        knowledge = self._load_knowledge()
        
        key = arguments.get("key", "")
        content = arguments.get("content", "")
        
        if not key or not content:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: key 和 content"
            }
        
        # 检查是否已存在相同 key 的知识
        existing = None
        for k in knowledge:
            if k.get("key") == key:
                existing = k
                break
        
        if existing:
            # 更新现有知识
            existing["content"] = content
            if "category" in arguments:
                existing["category"] = arguments["category"]
            if "tags" in arguments:
                existing["tags"] = arguments["tags"]
            if "metadata" in arguments:
                existing["metadata"] = arguments["metadata"]
            existing["updated_at"] = datetime.now().isoformat()
            knowledge_id = existing["id"]
        else:
            # 创建新知识
            knowledge_id = str(uuid.uuid4())
            new_knowledge = {
                "id": knowledge_id,
                "key": key,
                "content": content,
                "category": arguments.get("category", "general"),
                "tags": arguments.get("tags", []),
                "metadata": arguments.get("metadata", {}),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            knowledge.append(new_knowledge)
        
        self._save_knowledge(knowledge)
        
        return {
            "success": True,
            "content": {
                "id": knowledge_id,
                "key": key,
                "stored_at": datetime.now().isoformat()
            },
            "error": None
        }
    
    def _retrieve_knowledge(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """检索知识条目"""
        knowledge = self._load_knowledge()
        
        # 精确匹配 key
        key = arguments.get("key")
        if key:
            for k in knowledge:
                if k.get("key") == key:
                    return {
                        "success": True,
                        "content": {
                            "results": [k],
                            "total": len(knowledge),
                            "matched": 1
                        },
                        "error": None
                    }
            return {
                "success": True,
                "content": {
                    "results": [],
                    "total": len(knowledge),
                    "matched": 0
                },
                "error": None
            }
        
        # 模糊搜索
        query = arguments.get("query", "").lower()
        category_filter = arguments.get("category")
        tag_filter = arguments.get("tag")
        
        results = []
        for k in knowledge:
            # 分类过滤
            if category_filter and k.get("category") != category_filter:
                continue
            
            # 标签过滤
            if tag_filter and tag_filter not in k.get("tags", []):
                continue
            
            # 内容搜索
            if query:
                content = k.get("content", "").lower()
                key_lower = k.get("key", "").lower()
                if query in content or query in key_lower:
                    results.append(k)
            else:
                results.append(k)
        
        # 应用限制
        limit = arguments.get("limit")
        if limit:
            results = results[:limit]
        
        return {
            "success": True,
            "content": {
                "results": results,
                "total": len(knowledge),
                "matched": len(results)
            },
            "error": None
        }


def create_server(data_dir: str = None) -> KnowledgeServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        KnowledgeServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'knowledge_tool'
    
    data_path.mkdir(parents=True, exist_ok=True)
    
    return KnowledgeServer(data_path)

