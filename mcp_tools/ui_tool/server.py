#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 工具 MCP 服务器
符合 MCP 协议标准
"""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class UIServer:
    """UI 工具服务器"""
    
    def __init__(self, data_dir: Path):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录（UI 工具可能不需要存储）
        """
        self.data_dir = data_dir
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "ui.render":
            return self._render_ui(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _render_ui(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """渲染 UI 面板"""
        ui_type = arguments.get("type", "panel")
        
        ui_dsl = {
            "type": ui_type,
            "title": arguments.get("title", ""),
            "sections": arguments.get("sections", []),
            "data": arguments.get("data"),
            "config": arguments.get("config", {})
        }
        
        return {
            "success": True,
            "content": {
                "ui": ui_dsl,
                "rendered_at": datetime.now().isoformat()
            },
            "error": None
        }


def create_server(data_dir: str = None) -> UIServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        UIServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'ui_tool'
    
    data_path.mkdir(parents=True, exist_ok=True)
    
    return UIServer(data_path)

