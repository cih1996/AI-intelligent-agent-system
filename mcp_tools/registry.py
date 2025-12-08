#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具注册中心
动态扫描和加载所有 MCP 插件
"""

import json
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys
import asyncio


class MCPRegistry:
    """
    MCP 工具注册中心
    自动扫描 mcp_tools 目录下的所有插件并加载
    """
    
    def __init__(self, tools_dir: Optional[str] = None):
        """
        初始化注册中心
        
        Args:
            tools_dir: MCP 工具目录，默认为项目根目录下的 mcp_tools
        """
        if tools_dir:
            self.tools_dir = Path(tools_dir)
        else:
            # 默认工具目录
            project_root = Path(__file__).parent.parent
            self.tools_dir = project_root / 'mcp_tools'
        
        # 确保目录存在
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
        # 已加载的插件
        self.plugins: Dict[str, Dict[str, Any]] = {}
        
        # 工具注册表（工具名 -> 插件信息）
        self.tools: Dict[str, Dict[str, Any]] = {}
        
        print(f"[MCP Registry] 工具目录: {self.tools_dir}")
    
    def scan_plugins(self) -> List[str]:
        """
        扫描所有 MCP 插件
        
        Returns:
            插件名称列表
        """
        plugin_names = []
        
        if not self.tools_dir.exists():
            print(f"[MCP Registry] 警告: 工具目录不存在: {self.tools_dir}")
            return plugin_names
        
        # 扫描所有子目录
        for item in self.tools_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                # 检查是否包含 manifest.json
                manifest_file = item / 'manifest.json'
                if manifest_file.exists():
                    plugin_names.append(item.name)
        
        print(f"[MCP Registry] 发现 {len(plugin_names)} 个插件: {plugin_names}")
        return plugin_names
    
    def load_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        加载单个 MCP 插件
        
        Args:
            plugin_name: 插件目录名称
            
        Returns:
            插件信息字典
        """
        plugin_dir = self.tools_dir / plugin_name
        
        if not plugin_dir.exists():
            raise FileNotFoundError(f"插件目录不存在: {plugin_dir}")
        
        # 读取 manifest.json
        manifest_file = plugin_dir / 'manifest.json'
        if not manifest_file.exists():
            raise FileNotFoundError(f"插件缺少 manifest.json: {plugin_dir}")
        
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # 读取 tool.json
        tool_file = plugin_dir / 'tool.json'
        if not tool_file.exists():
            raise FileNotFoundError(f"插件缺少 tool.json: {plugin_dir}")
        
        with open(tool_file, 'r', encoding='utf-8') as f:
            tool_data = json.load(f)
        
        # 加载 server.py
        entry_file = plugin_dir / manifest.get('entry', 'server.py')
        if not entry_file.exists():
            raise FileNotFoundError(f"插件入口文件不存在: {entry_file}")
        
        # 动态导入插件服务器
        spec = importlib.util.spec_from_file_location(
            f"mcp_plugin_{plugin_name}",
            entry_file
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载插件: {plugin_name}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"mcp_plugin_{plugin_name}"] = module
        spec.loader.exec_module(module)
        
        # 获取插件服务器实例
        if not hasattr(module, 'create_server'):
            raise AttributeError(f"插件 {plugin_name} 缺少 create_server 函数")
        
        server = module.create_server()
        
        # 注册工具
        tools = tool_data.get('tools', [])
        for tool_def in tools:
            tool_name = tool_def.get('name')
            if tool_name:
                self.tools[tool_name] = {
                    'plugin': plugin_name,
                    'definition': tool_def,
                    'server': server
                }
                
        
        # 保存插件信息
        plugin_info = {
            'name': plugin_name,
            'manifest': manifest,
            'tools': tools,
            'server': server,
            'directory': plugin_dir
        }
        
        self.plugins[plugin_name] = plugin_info
        
        print(f"[MCP Registry] 已加载插件: {plugin_name} ({len(tools)} 个工具)")
        
        return plugin_info
    
    def load_all_plugins(self):
        """加载所有扫描到的插件"""
        plugin_names = self.scan_plugins()
        
        for plugin_name in plugin_names:
            try:
                self.load_plugin(plugin_name)
            except Exception as e:
                print(f"[MCP Registry] 加载插件失败 {plugin_name}: {str(e)}")
        
        print(f"[MCP Registry] 总共加载 {len(self.plugins)} 个插件，{len(self.tools)} 个工具")
    
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具信息
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具信息字典，如果不存在返回 None
        """
        return self.tools.get(tool_name)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具（直接调用，用于本地开发）
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        tool_info = self.get_tool(tool_name)
        
        if not tool_info:
            return {
                "success": False,
                "content": None,
                "error": f"工具不存在: {tool_name}"
            }
        
        server = tool_info['server']
        
        if not hasattr(server, 'call_tool'):
            return {
                "success": False,
                "content": None,
                "error": f"插件服务器不支持 call_tool 方法: {tool_info['plugin']}"
            }
        
        try:
            result = server.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"工具执行失败: {str(e)}"
            }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有已注册的工具（符合 MCP 协议格式）
        
        Returns:
            工具列表
        """
        tools_list = []
        for tool_name, tool_info in self.tools.items():
            tool_def = tool_info['definition']
            tools_list.append({
                "name": tool_def.get('name'),
                "description": tool_def.get('description'),
                "inputSchema": tool_def.get('input_schema', {})
            })
        
        return tools_list
    
    def get_tools_for_registration(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的注册信息（用于注册到 SimpleAIClient）
        
        Returns:
            工具注册信息列表
        """
        result = []
        for tool_name, tool_info in self.tools.items():
            tool_def = tool_info['definition']
            input_schema = tool_def.get('input_schema', {})
            properties = input_schema.get('properties', {})
            required = input_schema.get('required', [])
            
            # 转换为 SimpleAIClient 需要的格式
            parameters = {}
            for param_name, param_info in properties.items():
                parameters[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                    "required": param_name in required
                }
            
            result.append({
                "name": tool_name,
                "description": tool_def.get("description", ""),
                "parameters": parameters,
                "category": self._get_tool_category(tool_name)
            })
        
        return result
    
    def _get_tool_category(self, tool_name: str) -> str:
        """根据工具名称推断分类"""
        if '.' in tool_name:
            return tool_name.split('.')[0]
        return "general"
    
    def start_mcp_server(self, plugin_name: str, host: str = '127.0.0.1', port: int = None) -> None:
        """
        为指定插件启动标准 MCP HTTP 服务器
        
        Args:
            plugin_name: 插件名称
            host: 监听地址
            port: 监听端口（如果为 None，则自动分配）
        """
        if plugin_name not in self.plugins:
            raise ValueError(f"插件未加载: {plugin_name}")
        
        try:
            from mcp_tools.mcp_server import create_mcp_server_from_plugin
        except ImportError:
            print("[MCP Registry] 错误: 无法导入 mcp_server 模块")
            return
        
        plugin_info = self.plugins[plugin_name]
        http_server = create_mcp_server_from_plugin(plugin_info, host=host, port=port)
        
        # 运行服务器
        try:
            asyncio.run(http_server.run())
        except KeyboardInterrupt:
            print(f"\n[MCP Registry] {plugin_name} 服务器已停止")
    
    def start_all_mcp_servers(self, host: str = '127.0.0.1', base_port: int = 8000) -> None:
        """
        为所有已加载的插件启动标准 MCP HTTP 服务器
        
        Args:
            host: 监听地址
            base_port: 基础端口号（每个插件会分配不同的端口）
        """
        if not self.plugins:
            print("[MCP Registry] 没有已加载的插件")
            return
        
        try:
            from mcp_tools.mcp_server import create_mcp_server_from_plugin
        except ImportError:
            print("[MCP Registry] 错误: 无法导入 mcp_server 模块")
            return
        
        import asyncio
        
        async def run_all_servers():
            tasks = []
            current_port = base_port
            
            for plugin_name, plugin_info in self.plugins.items():
                http_server = create_mcp_server_from_plugin(plugin_info, host=host, port=current_port)
                tasks.append(http_server.run())
                current_port += 1
            
            # 并发运行所有服务器
            await asyncio.gather(*tasks)
        
        try:
            asyncio.run(run_all_servers())
        except KeyboardInterrupt:
            print("\n[MCP Registry] 所有服务器已停止")

