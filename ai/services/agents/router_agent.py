#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路由 AI Agent
负责为任务选择合适的 MCP 工具插件
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.simple_client import SimpleAIClient


class RouterAgent:
    """
    路由 AI Agent
    负责：
    - 分析任务描述
    - 从可用插件列表中选择最合适的插件
    - 支持多插件推荐
    """
    
    def __init__(self, provider: str = 'deepseek', history_file: str = "default", **kwargs):
        """
        初始化路由 AI Agent
        
        Args:
            provider: AI 服务商名称
            history_file: 历史对话文件路径
            **kwargs: 其他参数
        """
        self.client = SimpleAIClient(
            name="路由AI",
            prompt_file='prompts/mcp_tool_router.txt',
            provider=provider,
            history_file=history_file,
            **kwargs
        )
        self.system_prompt = self.client.system_prompt
    
    def _parse_json_array_from_response(self, response_text: str) -> Optional[List[str]]:
        """
        从AI响应中解析JSON数组（插件名称数组）
        
        Args:
            response_text: AI响应文本
            
        Returns:
            解析后的字符串数组，如果解析失败返回None
        """
        # 尝试直接解析 JSON
        try:
            data = json.loads(response_text.strip())
            if isinstance(data, list) and all(isinstance(item, str) for item in data):
                return data
        except:
            pass
        
        # 尝试从代码块中提取
        code_block_pattern = r'```(?:json)?\s*(\[.*?\])?\s*```'
        matches = re.findall(code_block_pattern, response_text, re.DOTALL)
        for match in matches:
            if match:
                try:
                    data = json.loads(match.strip())
                    if isinstance(data, list) and all(isinstance(item, str) for item in data):
                        return data
                except:
                    continue
        
        # 尝试查找 JSON 数组（使用括号匹配）
        bracket_count = 0
        start_idx = -1
        
        for i, char in enumerate(response_text):
            if char == '[':
                if bracket_count == 0:
                    start_idx = i
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0 and start_idx != -1:
                    json_str = response_text[start_idx:i+1]
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, list) and all(isinstance(item, str) for item in data):
                            return data
                    except:
                        pass
                    start_idx = -1
        
        return None
    
    def find_plugins(
        self,
        task_description: str,
        mcp_client_manager,
    ) -> Dict[str, Any]:
        """
        查找适合任务的 MCP 工具插件
        
        Args:
            task_description: 任务描述
            mcp_client_manager: MCPClientManager 实例
            max_plugins: 最大推荐插件数
            
        Returns:
            包含插件信息和状态的字典，格式: {
                'success': bool,
                'plugins': List[Dict],  # 推荐的插件信息列表（如果成功）
                'message': str,   # 状态消息
                'ai_response': str  # AI 的原始响应
            }
        """
        # 获取所有工具信息（按插件分组）
        plugins_text = mcp_client_manager.format_plugins_summary()
        # 更新系统提示词（注入插件列表）
        self.client.update_system_prompt({'{MCP_PLUGINS}': plugins_text})
        self.client.clear_history()
    
        # 构建路由输入
        router_input = (
            "用户任务: " + str(task_description) + "\n\n"
            "请从上述插件列表中选择最合适的插件，返回JSON数组格式。"
        )
        
        # 调用路由 AI
        response = self.client.chat(
            content=router_input,
            max_tokens=200,
            temperature=0.3,
        )
        
        router_ai_response = response.get("content", "")
        print("[路由AI] AI响应可选择的插件名称: ", router_ai_response)

        if not response.get("success") or not router_ai_response:
            error_msg = response.get('message', '未知错误')
            return {
                'success': False,
                'plugins': [],
                'message': error_msg,
                'ai_response': router_ai_response
            }
        
        # 从响应中解析JSON数组
        ai_plugin_names = self._parse_json_array_from_response(router_ai_response)
        
        if not ai_plugin_names:
            return {
                'success': False,
                'plugins': [],
                'message': '无法从 AI 响应中解析JSON数组格式的插件名称',
                'ai_response': router_ai_response
            }
        
        # 获取所有可用插件列表
        plugins_list = mcp_client_manager.get_tools()
        
        # 构建插件名称到插件信息的映射（支持多种格式匹配）
        plugins_map = {}
        plugins_normalized_map = {}  # 用于下划线和连字符的转换匹配
        
        for tool in plugins_list:
            plugin_name = tool.get('name') or tool.get('server', 'unknown')
            plugin_info = {
                "name": plugin_name,
                "description": tool.get('description', ''),
                "tools": tool.get('tools', [])
            }
            
            # 原始名称（小写）
            plugins_map[plugin_name.lower()] = plugin_info
            # 下划线版本（小写）
            plugins_normalized_map[plugin_name.replace("-", "_").lower()] = plugin_info
            # 连字符版本（小写）
            plugins_normalized_map[plugin_name.replace("_", "-").lower()] = plugin_info
        
        # 验证AI返回的插件名称是否存在
        recommended_plugins = []
        not_exist_plugins = []
        
        for ai_plugin_name in ai_plugin_names:
            ai_plugin_name = ai_plugin_name.strip()
            normalized_name = ai_plugin_name.lower()
            
            # 先尝试直接匹配
            plugin_info = plugins_map.get(normalized_name)
            
            # 如果直接匹配失败，尝试下划线和连字符转换后的匹配
            if not plugin_info:
                plugin_info = plugins_normalized_map.get(normalized_name.replace("_", "-"))
            if not plugin_info:
                plugin_info = plugins_normalized_map.get(normalized_name.replace("-", "_"))
            
            if plugin_info:
                # 避免重复添加
                if not any(p['name'].lower() == plugin_info['name'].lower() for p in recommended_plugins):
                    recommended_plugins.append(plugin_info)
            else:
                not_exist_plugins.append(ai_plugin_name)
        
        if not_exist_plugins:
            return {
                'success': False,
                'plugins': [],
                'message': f"AI 响应的以下插件不存在: {', '.join(not_exist_plugins)}",
                'ai_response': router_ai_response
            }
        
        if not recommended_plugins:
            return {
                'success': False,
                'plugins': [],
                'message': '无法从 AI 响应中找到有效的插件名称',
                'ai_response': router_ai_response
            }
        
        # 成功返回
        return {
            'success': True,
            'plugins': recommended_plugins,
            'message': f'成功找到 {len(recommended_plugins)} 个推荐插件',
            'ai_response': router_ai_response
        }


