#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
标准 MCP 服务器实现
符合 Model Context Protocol 标准
支持 HTTP 传输，可部署到外网
"""

import json
import sys
import asyncio
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import traceback


class MCPServer:
    """
    标准 MCP 服务器
    实现 JSON-RPC 2.0 协议，符合 MCP 标准
    """
    
    def __init__(self, name: str, version: str = "1.0.0", plugin_info: Optional[Dict[str, Any]] = None):
        """
        初始化 MCP 服务器
        
        Args:
            name: 服务器名称
            version: 服务器版本
            plugin_info: 插件信息（包含 manifest），用于在工具列表中附加插件信息
        """
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.tool_handlers: Dict[str, Callable] = {}
        self.request_id = 0
        self.plugin_info = plugin_info or {}  # 保存插件信息（manifest等）
        # 会话级别的上下文对象（在 initialize 时设置）
        # 可以包含任意键值对，如 user_id, tenant_id, workspace_id 等
        self.context: Optional[Dict[str, Any]] = None
        
    def register_tool(self, tool_def: Dict[str, Any], handler: Callable):
        """
        注册工具
        
        Args:
            tool_def: 工具定义（包含 name, description, inputSchema）
            handler: 工具处理函数
        """
        tool_name = tool_def.get('name')
        if not tool_name:
            raise ValueError("工具定义必须包含 'name' 字段")
        
        self.tools[tool_name] = tool_def
        self.tool_handlers[tool_name] = handler
    
    async def handle_request(self, request: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理 JSON-RPC 请求
        
        Args:
            request: JSON-RPC 请求
            user_context: 用户上下文（包含 user_id, session_id 等），用于数据隔离
            
        Returns:
            JSON-RPC 响应
        """
        method = request.get('method')
        params = request.get('params', {})
        request_id = request.get('id')
        
        try:
            if method == 'initialize':
                return self._handle_initialize(request_id, params)
            elif method == 'tools/list':
                return self._handle_list_tools(request_id, self.plugin_info)
            elif method == 'tools/call':
                return await self._handle_call_tool(request_id, params, user_context)
            elif method == 'ping':
                return {'jsonrpc': '2.0', 'id': request_id, 'result': 'pong'}
            else:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {method}'
                    }
                }
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}',
                    'data': traceback.format_exc()
                }
            }
    
    def _handle_initialize(self, request_id: Optional[int], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理 initialize 请求
        
        从 params 中提取 context，保存到会话级别，用于后续所有工具调用的数据隔离
        支持任意键值对，如 user_id, tenant_id, workspace_id 等
        
        如果manifest中定义了requiredContext，会验证必需的参数是否提供
        """
        # 从初始化参数中提取上下文对象（用于数据隔离）
        # 只支持标准的 context 字段，从 mcp.json 配置中获取
        context = params.get('context', {})
        
        # 验证必需的上下文参数（如果manifest中定义了requiredContext）
        manifest = self.plugin_info.get('manifest', {})
        required_context = manifest.get('requiredContext', {})
        
        if required_context:
            missing_params = []
            for param_name, param_def in required_context.items():
                if param_def.get('required', False):
                    if param_name not in context or not context[param_name]:
                        missing_params.append(param_name)
            
            if missing_params:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32602,
                        'message': f'Missing required context parameters: {", ".join(missing_params)}. Please configure them in mcp.json',
                        'data': {
                            'requiredContext': required_context,
                            'missing': missing_params
                        }
                    }
                }
        
        # 保存上下文对象到会话级别
        if context:
            self.context = context
        
        # 构建返回结果，包含插件信息
        result = {
            'protocolVersion': '2024-11-05',
            'capabilities': {
                'tools': {}
            },
            'serverInfo': {
                'name': self.name,
                'version': self.version
            }
        }
        
        # 从 plugin_info 中获取插件描述和 requiredContext
        manifest = self.plugin_info.get('manifest', {})
        if manifest:
            # 添加插件描述
            description = manifest.get('description')
            if description:
                result['serverInfo']['description'] = description
            
            # 添加必需的上下文参数信息（requiredContext）
            required_context = manifest.get('requiredContext')
            if required_context:
                result['requiredContext'] = required_context
        
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': result
        }
    
    def _handle_list_tools(self, request_id: Optional[int], plugin_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """处理 tools/list 请求"""
        tools_list = []
        for tool_name, tool_def in self.tools.items():
            tool_item = {
                'name': tool_def.get('name'),
                'description': tool_def.get('description', ''),
                'inputSchema': tool_def.get('input_schema', tool_def.get('inputSchema', {}))
            }
            tools_list.append(tool_item)
        
        result = {
            'tools': tools_list
        }
        
        # 在顶层附加插件信息（不破坏 MCP 标准，作为额外字段）
        if plugin_info:
            plugin_metadata = {
                'name': plugin_info.get('name', self.name),
                'version': plugin_info.get('version', self.version),
                'description': plugin_info.get('description', '')
            }
            # 如果manifest中有requiredContext，也包含在plugin信息中
            manifest = plugin_info.get('manifest', {})
            if 'requiredContext' in manifest:
                plugin_metadata['requiredContext'] = manifest['requiredContext']
            
            result['plugin'] = plugin_metadata
        
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': result
        }
    
    async def _handle_call_tool(self, request_id: Optional[int], params: Dict[str, Any], request_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理 tools/call 请求
        
        Args:
            request_id: 请求ID
            params: 请求参数
            request_context: 未使用（保留接口兼容性）
        """
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        # mcp_server.py 只负责原封不动地传递数据
        # 将会话级别的上下文（从 initialize 中获取）注入到工具参数中
        # 每个工具的 server.py 自己负责从 _context 中提取并校验必需的参数
        if self.context:
            arguments['_context'] = self.context
        
        if not tool_name:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32602,
                    'message': 'Missing required parameter: name'
                }
            }
        
        if tool_name not in self.tool_handlers:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'Tool not found: {tool_name}'
                }
            }
        
        handler = self.tool_handlers[tool_name]
        
        try:
            # 调用工具处理函数
            if asyncio.iscoroutinefunction(handler):
                result = await handler(arguments)
            else:
                result = handler(arguments)
            
            # 转换结果为 MCP 标准格式
            if isinstance(result, dict):
                if 'success' in result:
                    # 兼容现有格式
                    if result.get('success'):
                        content = result.get('content')
                        if isinstance(content, str):
                            content_text = content
                        elif isinstance(content, dict):
                            content_text = json.dumps(content, ensure_ascii=False, indent=2)
                        else:
                            content_text = str(content)
                        
                        return {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'content': [
                                    {
                                        'type': 'text',
                                        'text': content_text
                                    }
                                ],
                                'isError': False
                            }
                        }
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        return {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'content': [
                                    {
                                        'type': 'text',
                                        'text': f'Error: {error_msg}'
                                    }
                                ],
                                'isError': True
                            }
                        }
                else:
                    # 直接返回结果
                    content_text = json.dumps(result, ensure_ascii=False, indent=2)
                    return {
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'result': {
                            'content': [
                                {
                                    'type': 'text',
                                    'text': content_text
                                }
                            ],
                            'isError': False
                        }
                    }
            else:
                # 非字典结果，转换为文本
                content_text = json.dumps(result, ensure_ascii=False, indent=2) if not isinstance(result, str) else result
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {
                        'content': [
                            {
                                'type': 'text',
                                'text': content_text
                            }
                        ],
                        'isError': False
                    }
                }
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'content': [
                        {
                            'type': 'text',
                            'text': f'Tool execution error: {str(e)}\n{traceback.format_exc()}'
                        }
                    ],
                    'isError': True
                }
            }


class HTTPMCPServer:
    """
    HTTP 传输的 MCP 服务器
    监听指定端口，提供 HTTP API
    """
    
    def __init__(self, mcp_server: MCPServer, host: str = '127.0.0.1', port: int = 8000, plugin_info: Optional[Dict[str, Any]] = None):
        """
        初始化 HTTP MCP 服务器
        
        Args:
            mcp_server: MCP 服务器实例
            host: 监听地址
            port: 监听端口
            plugin_info: 插件信息（包含 manifest），用于在工具列表中附加插件信息
        """
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.plugin_info = plugin_info or {}  # 保存插件信息（manifest等）
    
    async def handle_http_request(self, method: str, path: str, body: bytes, headers: Dict[str, str]) -> tuple[int, Dict[str, str], bytes]:
        """
        处理 HTTP 请求
        
        Returns:
            (status_code, headers, body)
        """
        # mcp_server.py 只负责原封不动地传递数据，不做任何上下文提取或处理
        # 上下文参数应该通过 initialize 时的 context 字段传递（从 mcp.json 配置中获取）
        
        # 设置 CORS 头
        cors_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        if method == 'OPTIONS':
            return (200, cors_headers, b'')
        
        if method == 'GET' and path == '/health':
            response = {'status': 'ok', 'name': self.mcp_server.name, 'version': self.mcp_server.version}
            return (200, cors_headers, json.dumps(response, ensure_ascii=False).encode('utf-8'))
        
        if method == 'GET' and path == '/tools':
            # 列出所有工具
            tools_list = []
            for tool_name, tool_def in self.mcp_server.tools.items():
                tool_item = {
                    'name': tool_def.get('name'),
                    'description': tool_def.get('description', ''),
                    'inputSchema': tool_def.get('input_schema', tool_def.get('inputSchema', {}))
                }
                tools_list.append(tool_item)
            
            response = {'tools': tools_list}
            
            # 在顶层附加插件信息（不破坏 MCP 标准，作为额外字段）
            if self.plugin_info:
                response['plugin'] = {
                    'name': self.plugin_info.get('name', self.mcp_server.name),
                    'version': self.plugin_info.get('version', self.mcp_server.version),
                    'description': self.plugin_info.get('description', '')
                }
            
            return (200, cors_headers, json.dumps(response, ensure_ascii=False, indent=2).encode('utf-8'))
        
        if method == 'POST' and path == '/mcp':
            # 处理 JSON-RPC 请求（标准 MCP HTTP 端点）
            try:
                request = json.loads(body.decode('utf-8'))
                # 原封不动传递请求，不做任何上下文提取或处理
                response = await self.mcp_server.handle_request(request, None)
                return (200, cors_headers, json.dumps(response, ensure_ascii=False).encode('utf-8'))
            except json.JSONDecodeError as e:
                error_response = {
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32700,
                        'message': f'Parse error: {str(e)}'
                    }
                }
                return (400, cors_headers, json.dumps(error_response, ensure_ascii=False).encode('utf-8'))
        
        # MCP HTTP 传输端点（用于 Cursor streamable-http）
        # 支持 GET 和 POST，返回 JSON-RPC 响应
        if path == '/message' or (method == 'POST' and path == '/'):
            try:
                if method == 'GET':
                    # GET 请求可能用于健康检查或初始化
                    return (200, cors_headers, json.dumps({
                        'jsonrpc': '2.0',
                        'result': {
                            'protocolVersion': '2024-11-05',
                            'capabilities': {'tools': {}},
                            'serverInfo': {
                                'name': self.mcp_server.name,
                                'version': self.mcp_server.version
                            }
                        }
                    }, ensure_ascii=False).encode('utf-8'))
                else:
                    # POST 请求处理 JSON-RPC
                    request = json.loads(body.decode('utf-8'))
                    # 原封不动传递请求，不做任何上下文提取或处理
                    response = await self.mcp_server.handle_request(request, None)
                    return (200, cors_headers, json.dumps(response, ensure_ascii=False).encode('utf-8'))
            except json.JSONDecodeError as e:
                error_response = {
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32700,
                        'message': f'Parse error: {str(e)}'
                    }
                }
                return (400, cors_headers, json.dumps(error_response, ensure_ascii=False).encode('utf-8'))
        
        # 404
        return (404, cors_headers, json.dumps({'error': 'Not found'}, ensure_ascii=False).encode('utf-8'))
    
    async def run(self):
        """运行 HTTP 服务器（使用 asyncio）"""
        try:
            import aiohttp
            from aiohttp import web
        except ImportError:
            print("错误: 需要安装 aiohttp: pip install aiohttp")
            sys.exit(1)
        
        app = web.Application()
        
        async def handle_request(request):
            method = request.method
            path = request.path_qs.split('?')[0]  # 移除查询参数
            body = await request.read()
            headers = dict(request.headers)
            
            status, headers_dict, body_bytes = await self.handle_http_request(method, path, body, headers)
            
            response = web.Response(
                status=status,
                headers=headers_dict,
                body=body_bytes
            )
            return response
        
        # 标准 HTTP JSON-RPC 端点
        app.router.add_route('*', '/{path:.*}', handle_request)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        print(f"[MCP Server] {self.mcp_server.name} v{self.mcp_server.version} 启动成功 , HTTP 服务监听: http://{self.host}:{self.port}")

        # 保持运行
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\n[MCP Server] 正在关闭...")
            await runner.cleanup()


def create_mcp_server_from_plugin(plugin_info: Dict[str, Any], host: str = '127.0.0.1', port: int = None) -> HTTPMCPServer:
    """
    从插件信息创建标准 MCP 服务器
    
    Args:
        plugin_info: 插件信息（来自 MCPRegistry）
        host: 监听地址
        port: 监听端口（如果为 None，则自动分配）
        
    Returns:
        HTTPMCPServer 实例
    """
    plugin_name = plugin_info['name']  # 目录名（如 qq_tool）
    tools = plugin_info['tools']
    server_instance = plugin_info['server']
    manifest = plugin_info.get('manifest', {})
    
    # 使用 manifest.json 中的 name（如 qq-tool），如果没有则使用目录名
    manifest_name = manifest.get('name', plugin_name)
    
    # 准备插件信息（用于附加到工具列表和验证）
    plugin_metadata = {
        'name': manifest_name,
        'version': manifest.get('version', '1.0.0'),
        'description': manifest.get('description', ''),
        'manifest': manifest  # 包含完整的manifest，包括requiredContext
    }
    
    # 创建 MCP 服务器（使用 manifest.json 中的 name 和 version）
    mcp_server = MCPServer(
        name=manifest_name,  # 使用 manifest.json 中的 name，而不是目录名
        version=manifest.get('version', '1.0.0'),
        plugin_info=plugin_metadata
    )
    
    # 注册所有工具
    for tool_def in tools:
        tool_name = tool_def.get('name')
        if tool_name and hasattr(server_instance, 'call_tool'):
            # 创建工具处理函数（使用闭包捕获 tool_name）
            def make_handler(name):
                def handler(arguments):
                    return server_instance.call_tool(name, arguments)
                return handler
            
            # 立即调用以创建闭包
            handler = make_handler(tool_name)
            mcp_server.register_tool(tool_def, handler)
    
    # 如果未指定端口，使用默认端口（基于插件名称的哈希）
    if port is None:
        port = 8000 + (hash(plugin_name) % 1000)
    
    # 创建 HTTP 服务器（传递插件信息）
    return HTTPMCPServer(mcp_server, host=host, port=port, plugin_info=plugin_metadata)

