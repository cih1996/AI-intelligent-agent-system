#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP HTTP 客户端
通过 HTTP 调用标准 MCP 服务器
从 mcp.json 配置文件读取服务器信息
"""

import json
import os
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from pathlib import Path


class MCPHTTPClient:
    """
    MCP HTTP 客户端
    通过 HTTP 调用远程或本地的 MCP 服务器
    """
    
    def __init__(self, base_url: str, timeout: int = 30, context: Optional[Dict[str, Any]] = None):
        """
        初始化 MCP HTTP 客户端
        
        Args:
            base_url: MCP 服务器的基础 URL（如 http://127.0.0.1:8003）
            timeout: 请求超时时间（秒）
            context: 上下文对象（用于数据隔离，从 mcp.json 配置中读取）
                     可以包含任意键值对，如 user_id, tenant_id, workspace_id 等
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.context = context or {}
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def initialize(self) -> Dict[str, Any]:
        """
        初始化 MCP 连接
        
        Returns:
            初始化响应
        """
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "mcp-http-client",
                "version": "1.0.0"
            }
        }
        
        # 如果配置了上下文，在初始化参数中传递（用于会话级别的数据隔离）
        # 使用标准的 context 字段，支持任意键值对
        if self.context:
            params["context"] = self.context
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": params
        }
        
        return self._send_request(request)
    
    def list_tools(self) -> Dict[str, Any]:
        """
        列出所有可用工具
        
        Returns:
            工具列表响应
        """
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        return self._send_request(request)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果（转换为标准格式）
        """
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = self._send_request(request)
        
        # 转换 MCP 标准响应格式为内部格式
        if 'result' in response:
            result = response['result']
            if 'content' in result and isinstance(result['content'], list):
                # 提取文本内容
                content_text = ""
                for item in result['content']:
                    if item.get('type') == 'text':
                        content_text = item.get('text', '')
                        break
                
                # 尝试解析 JSON
                try:
                    content_data = json.loads(content_text)
                except:
                    content_data = content_text
                
                return {
                    "success": not result.get('isError', False),
                    "content": content_data,
                    "error": None if not result.get('isError', False) else content_text
                }
            else:
                return {
                    "success": True,
                    "content": result,
                    "error": None
                }
        elif 'error' in response:
            return {
                "success": False,
                "content": None,
                "error": response['error'].get('message', '未知错误')
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": "未知响应格式"
            }
    
    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送 JSON-RPC 请求
        
        Args:
            request: JSON-RPC 请求
            
        Returns:
            JSON-RPC 响应
        """
        # 尝试多个端点
        endpoints = ['/mcp', '/message', '/']
        
        for endpoint in endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.post(
                    url,
                    json=request,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if endpoint == endpoints[-1]:
                    # 最后一个端点也失败，返回错误
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get('id'),
                        "error": {
                            "code": -32603,
                            "message": f"HTTP 请求失败: {str(e)}"
                        }
                    }
                continue
        
        return {
            "jsonrpc": "2.0",
            "id": request.get('id'),
            "error": {
                "code": -32603,
                "message": "所有端点都失败"
            }
        }
    
    def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            服务器是否健康
        """
        try:
            url = urljoin(self.base_url, '/health')
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False


class MCPClientManager:
    """
    MCP 客户端管理器
    从 mcp.json 配置文件读取服务器信息并管理所有 MCP 客户端
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化客户端管理器
        
        Args:
            config_path: mcp.json 配置文件路径，默认为项目根目录下的 mcp.json
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 默认配置文件路径
            project_root = Path(__file__).parent.parent.parent
            self.config_path = project_root / 'config/mcp.json'
        
        # 服务器配置（从配置文件读取）
        self.server_configs: Dict[str, Dict[str, Any]] = {}
        
        # HTTP 客户端字典 {server_name: MCPHTTPClient}
        self.clients: Dict[str, MCPHTTPClient] = {}
        
        # 工具到服务器的映射 {tool_name: server_name}
        self.tool_to_server: Dict[str, str] = {}
        
        # 插件信息字典 {server_name: {'name': ..., 'description': ..., 'requiredContext': ...}}
        self.plugins_info: Dict[str, Dict[str, Any]] = {}
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """从 mcp.json 加载配置"""
        if not self.config_path.exists():
            print(f"⚠ 警告: 配置文件不存在: {self.config_path}")
            print("  请创建 mcp.json 配置文件，格式如下：")
            print("  {")
            print('    "mcpServers": {')
            print('      "server-name": {')
            print('        "url": "http://127.0.0.1:8003",')
            print('        "transport": "streamable-http"')
            print("      }")
            print("    }")
            print("  }")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            mcp_servers = config.get('mcpServers', {})
            
            for server_name, server_config in mcp_servers.items():
                url = server_config.get('url')
                transport = server_config.get('transport', 'streamable-http')
                
                if not url:
                    print(f"⚠ 警告: 服务器 '{server_name}' 缺少 url 配置")
                    continue
                
                if transport != 'streamable-http':
                    print(f"⚠ 警告: 服务器 '{server_name}' 使用不支持的传输方式: {transport}")
                    continue
                
                # 从配置中读取上下文对象（用于数据隔离）
                # context 对象包含系统级参数，如 user_id, api_key, license_key 等
                context = server_config.get('context', {})
                
                self.server_configs[server_name] = {
                    'url': url,
                    'transport': transport,
                    'context': context
                }
                
                # 创建 HTTP 客户端（传递上下文对象）
                client = MCPHTTPClient(url, context=context if context else None)
                self.clients[server_name] = client
            
            print(f"[MCP Client Manager] 从 {self.config_path} 加载了 {len(self.clients)} 个 MCP 服务器")
            
        except json.JSONDecodeError as e:
            print(f"✗ 错误: 配置文件 JSON 格式错误: {e}")
        except Exception as e:
            print(f"✗ 错误: 加载配置文件失败: {e}")
    
    def initialize_all(self):
        """初始化所有服务器连接并获取工具列表"""
        print("\n[初始化] 正在连接 MCP 服务器...")
        
        for server_name, client in self.clients.items():
            try:
                # 初始化连接
                init_result = client.initialize()
                if 'error' in init_result:
                    error_msg = init_result['error'].get('message', '未知错误')
                    error_data = init_result['error'].get('data', {})
                    # 如果是缺少必需上下文参数的错误，提供更详细的提示
                    if 'Missing required context parameters' in error_msg:
                        missing = error_data.get('missing', [])
                        required = error_data.get('requiredContext', {})
                        print(f"  ✗ {server_name}: 初始化失败 - {error_msg}")
                        print(f"     请在 mcp.json 中为 '{server_name}' 配置以下必需的上下文参数：")
                        for param_name in missing:
                            param_def = required.get(param_name, {})
                            param_desc = param_def.get('description', '')
                            print(f"       - {param_name}: {param_desc}")
                        print(f"     示例配置：")
                        print(f"       \"{server_name}\": {{")
                        print(f"         \"url\": \"...\",")
                        print(f"         \"transport\": \"streamable-http\",")
                        print(f"         \"context\": {{")
                        for param_name in missing:
                            print(f"           \"{param_name}\": \"your-value\"")
                        print(f"         }}")
                        print(f"       }}")
                    else:
                        print(f"  ✗ {server_name}: 初始化失败 - {error_msg}")
                    continue
                
                # 从 initialize 响应中提取插件信息和 requiredContext
                init_result_data = init_result.get('result', {})
                server_info = init_result_data.get('serverInfo', {})
                plugin_name = server_info.get('name', server_name)
                plugin_description = server_info.get('description', '')
                required_context = init_result_data.get('requiredContext', {})
                
                # 校验 requiredContext：检查 mcp.json 是否提供了所有必需的参数
                if required_context:
                    context_config = self.server_configs[server_name].get('context', {})
                    missing_params = []
                    for param_name, param_def in required_context.items():
                        if param_def.get('required', False):
                            if param_name not in context_config or not context_config[param_name]:
                                missing_params.append(param_name)
                    
                    if missing_params:
                        # 直接报错，不继续初始化
                        print(f"  ✗ {server_name} ({plugin_name}): 缺少必需的上下文参数")
                        print(f"     请在 mcp.json 中为 '{server_name}' 配置以下必需的上下文参数：")
                        for param_name in missing_params:
                            param_def = required_context.get(param_name, {})
                            param_desc = param_def.get('description', '')
                            print(f"       - {param_name}: {param_desc}")
                        print(f"     示例配置：")
                        print(f"       \"{server_name}\": {{")
                        print(f"         \"url\": \"{self.server_configs[server_name].get('url')}\",")
                        print(f"         \"transport\": \"streamable-http\",")
                        print(f"         \"context\": {{")
                        for param_name in missing_params:
                            print(f"           \"{param_name}\": \"your-value\"")
                        print(f"         }}")
                        print(f"       }}")
                        continue  # 跳过这个服务器，不继续初始化
                
                
                
                # 获取工具列表
                tools_result = client.list_tools()
                if 'result' in tools_result:
                    tools = tools_result['result'].get('tools', [])
                   
                    for tool in tools:
                        tool_name = tool.get('name')
                        if tool_name:
                            self.tool_to_server[tool_name] = server_name
                    
                    print(f"  ✓ {server_name} ({plugin_name}): 连接成功，已注册 {len(tools)} 个工具")
                else:
                    print(f"  ⚠ {server_name} ({plugin_name}): 连接成功，但无法获取工具列表")

                # 保存插件信息到成员变量
                self.plugins_info[server_name] = {
                    'name': plugin_name,
                    'description': plugin_description,
                    'tools':tools,
                    'requiredContext': required_context
                }
                    
            except Exception as e:
                print(f"  ✗ {server_name}: 连接失败 - {str(e)}")
        
    
    def get_client_for_tool(self, tool_name: str) -> Optional[MCPHTTPClient]:
        """
        根据工具名称获取对应的客户端
        
        Args:
            tool_name: 工具名称（如 system.get_windows）
            
        Returns:
            MCP HTTP 客户端，如果未找到返回 None
        """
        server_name = self.tool_to_server.get(tool_name)
        if server_name and server_name in self.clients:
            return self.clients[server_name]
        
        # 尝试从工具名称推断服务器名称
        if '.' in tool_name:
            prefix = tool_name.split('.')[0]
            # 尝试匹配服务器名称
            for server_name, client in self.clients.items():
                if prefix in server_name or server_name.startswith(prefix):
                    self.tool_to_server[tool_name] = server_name
                    return client
        
        return None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具（自动路由到正确的服务器）
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        client = self.get_client_for_tool(tool_name)
        
        if not client:
            # 获取前10个可用工具名称
            available_tools = list(self.tool_to_server.keys())
            return {
                "success": False,
                "content": None,
                "error": f"未找到工具 '{tool_name}' 对应的服务器。可用工具: {', '.join(available_tools)}"
            }
        
        return client.call_tool(tool_name, arguments)
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        获取所有可用工具
        
        Returns:
            工具列表（每个工具包含 plugin 字段，从顶层 plugin 信息获取）
        """
        all_tools = []
        
        for server_name, client in self.clients.items():
            try:
                tools_result = client.list_tools()
                if 'result' in tools_result:
                    result = tools_result['result']
                    tools = result.get('tools', [])
                    
                    # 从顶层获取插件信息
                    plugin_info = result.get('plugin', {})
                    if not plugin_info:
                        # 如果没有 plugin 信息，从服务器配置中创建
                        plugin_info = {
                            'name': server_name,
                            'version': '1.0.0',
                            'description': f'MCP 服务器: {server_name}'
                        }
                    
                    for tool in tools:
                        # 设置服务器名称（用于向后兼容）
                        tool['server'] = server_name
                        # 附加插件信息到每个工具（用于路由AI识别）
                        tool['plugin'] = plugin_info
                        all_tools.append(tool)
            except Exception as e:
                # 调试：打印错误信息
                print(f"  ⚠ 获取 {server_name} 的工具列表失败: {str(e)}")
                pass
        
        return all_tools

    def get_tools(self) -> List[Dict[str, str]]:
        """
        获取所有插件的名称和描述列表（不包含具体的工具方法）
        Returns:
            插件列表，每个元素包含 'name' 和 'description' 字段
            格式: [{'name': 'qq-tool', 'description': 'QQ消息管理 MCP 工具'}, ...]
        """
        plugins_list = []
        
        # 使用缓存的插件信息（从 initialize_all 中获取）
        for server_name, plugin_info in self.plugins_info.items():
            plugin_name = plugin_info.get('name', server_name)
            description = plugin_info.get('description', '')
            tools = plugin_info.get('tools', [])
            
            plugins_list.append({
                'name': plugin_name,
                'description': description,
                'tools': tools
            })
        
        return plugins_list

    # 插件列表格式化（供 Agent/前端友好展示）
    def format_plugins_summary(self) -> str:
        """
        获取所有插件的概要描述（每个插件一行，格式：- 插件名: 描述）
        使用 get_tools() 方法获取插件列表，避免代码重复

        Returns:
            格式化字符串，每行为 "- 插件名: 描述"
        """
        plugins_list = self.get_tools()
        
        plugins_text = "\n".join([
            f"- {p['name']}: {p['description']}"
            for p in plugins_list
        ])

        if not plugins_text:
            plugins_text = "（暂无可用插件）"

        return plugins_text