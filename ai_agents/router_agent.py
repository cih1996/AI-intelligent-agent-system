#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路由 AI Agent
负责为任务选择合适的 MCP 工具插件
"""

from typing import Dict, Any, List
from datetime import datetime
from .base_agent import BaseAgent


class RouterAgent(BaseAgent):
    """
    路由 AI Agent
    负责：
    - 分析任务描述
    - 从可用插件列表中选择最合适的插件
    - 支持多插件推荐
    """
    
    def __init__(self, provider: str = 'deepseek', **kwargs):
        """
        初始化路由 AI Agent
        
        Args:
            provider: AI 服务商名称
            **kwargs: 其他参数
        """
        super().__init__(
            name="路由AI",
            prompt_file='prompts/mcp_tool_router.txt',
            provider=provider,
            **kwargs
        )
    
    def find_plugins(
        self,
        task_description: str,
        mcp_client_manager,
        max_plugins: int = 5
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
        plugins_summary = []
        plugin_tools = {}  # {plugin_name: [tools]}
        
        all_tools = mcp_client_manager.get_all_tools()
        
        # 调试：检查工具列表是否为空
        if not all_tools:
            print(f"⚠ 警告: mcp_client_manager.get_all_tools() 返回空列表")
            print(f"  可用客户端: {list(mcp_client_manager.clients.keys())}")
            # 如果工具列表为空，至少列出服务器名称
            for server_name in mcp_client_manager.clients.keys():
                plugins_summary.append({
                    'name': server_name,
                    'description': f"MCP 服务器: {server_name}",
                })
        else:
            # 按插件分组（优先使用 tool.plugin.name，否则使用 tool.server）
            for tool in all_tools:
                # 优先使用 plugin 字段中的名称
                plugin_info = tool.get('plugin', {})
                plugin_name = plugin_info.get('name') or tool.get('server', 'unknown')
                
                if plugin_name not in plugin_tools:
                    plugin_tools[plugin_name] = []
                plugin_tools[plugin_name].append(tool)
            
            # 构建插件摘要（每个插件作为一个条目）
            for plugin_name, tools in plugin_tools.items():
                # 从第一个工具的 plugin 信息中获取描述
                plugin_info = tools[0].get('plugin', {})
                description = plugin_info.get('description', f"提供 {len(tools)} 个工具")
                
                plugins_summary.append({
                    'name': plugin_name,
                    'description': description,
                })
        
        # 格式化插件列表
        plugins_text = "\n".join([
            f"- {p['name']}: {p['description']}"
            for p in plugins_summary
        ])
        
        # 如果插件列表仍然为空，提供默认提示
        if not plugins_text:
            plugins_text = "（暂无可用插件）"
        
        # 更新系统提示词（注入插件列表）
        if '{MCP_PLUGINS}' not in self.system_prompt:
            print(f"⚠ 警告: 系统提示词中未找到 {{MCP_PLUGINS}} 占位符")
            updated_prompt = self.system_prompt
        else:
            updated_prompt = self.system_prompt.replace('{MCP_PLUGINS}', plugins_text)
  
        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_weekday = datetime.now().strftime("%A")
        
        # 构建路由输入
        router_input = f"""[当前时间: {current_time} ({current_date} {current_weekday})]

用户任务: {task_description} 

请从上述插件列表中选择最合适的插件（如果任务需要多个插件协作，请返回多个插件名称，每行一个）。"""
        
        # 调用路由 AI
        response = self.chat_with_messages(
            messages=[
                {"role": "system", "content": updated_prompt},
                {"role": "user", "content": router_input}
            ],
            max_tokens=200,
            temperature=0.3,
            use_history=False
        )
        
        router_ai_response = response.get("content", "")
        
        if not response.get("success") or not router_ai_response:
            error_msg = response.get('message', '未知错误')
            return {
                'success': False,
                'plugins': [],
                'message': error_msg,
                'ai_response': router_ai_response
            }
        
        # 从响应中提取推荐的插件名称
        recommended_plugin_names = self._extract_plugin_names(router_ai_response, plugins_summary)
        
        if not recommended_plugin_names:
            return {
                'success': False,
                'plugins': [],
                'message': '无法从 AI 响应中提取插件名称',
                'ai_response': router_ai_response
            }
        
        # 返回插件信息（从 mcp_client_manager 获取）
        result_plugins = []
        all_tools = mcp_client_manager.get_all_tools()
        plugin_tools_map = {}  # {plugin_name: [tools]}
        
        # 按插件分组（使用 tool.plugin.name）
        for tool in all_tools:
            plugin_info = tool.get('plugin', {})
            plugin_name = plugin_info.get('name') or tool.get('server', 'unknown')
            
            if plugin_name not in plugin_tools_map:
                plugin_tools_map[plugin_name] = []
            plugin_tools_map[plugin_name].append(tool)
        
        for plugin_name in recommended_plugin_names[:max_plugins]:
            # 匹配插件名称（支持连字符和下划线互换）
            matched_plugin = None
            for p_name in plugin_tools_map.keys():
                if (plugin_name == p_name or 
                    plugin_name.replace('-', '_') == p_name.replace('-', '_') or
                    plugin_name.replace('_', '-') == p_name.replace('_', '-')):
                    matched_plugin = p_name
                    break
            
            if matched_plugin:
                tools = plugin_tools_map[matched_plugin]
                # 从第一个工具的 plugin 信息中获取描述
                plugin_info = tools[0].get('plugin', {}) if tools else {}
                description = plugin_info.get('description', f"提供 {len(tools)} 个工具")
                
                result_plugins.append({
                    'name': matched_plugin,
                    'description': description,
                    'plugin_info': {
                        'name': matched_plugin,
                        'tools': tools
                    }
                })
        
        if not result_plugins:
            return {
                'success': False,
                'plugins': [],
                'message': f'AI 推荐的插件在注册表中不存在: {recommended_plugin_names}',
                'ai_response': router_ai_response
            }
        
        return {
            'success': True,
            'plugins': result_plugins,
            'message': f'成功找到 {len(result_plugins)} 个推荐插件',
            'ai_response': router_ai_response
        }
    
    def _extract_plugin_names(self, response: str, plugins_summary: List[Dict]) -> List[str]:
        """
        从 AI 响应中提取插件名称
        
        Args:
            response: AI 响应文本
            plugins_summary: 插件摘要列表
            
        Returns:
            提取到的插件名称列表
        """
        import re
        recommended_plugin_names = []
        response_lower = response.lower().strip()
        
        # 方法1: 精确匹配插件名称（支持连字符和下划线互换）
        for plugin_info in plugins_summary:
            plugin_name = plugin_info['name']
            plugin_name_lower = plugin_name.lower()
            
            # 检查响应中是否包含插件名称（支持连字符和下划线互换）
            normalized_plugin_name = plugin_name_lower.replace('_', '-')
            normalized_response = response_lower.replace('_', '-')
            
            # 尝试匹配原始名称
            pattern1 = r'\b' + re.escape(plugin_name_lower) + r'\b'
            # 尝试匹配连字符版本
            pattern2 = r'\b' + re.escape(normalized_plugin_name) + r'\b'
            
            if re.search(pattern1, response_lower) or re.search(pattern2, normalized_response):
                if plugin_name not in recommended_plugin_names:
                    recommended_plugin_names.append(plugin_name)
        
        # 方法2: 如果方法1没找到，尝试逐行提取
        if not recommended_plugin_names:
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 移除可能的编号前缀
                line = re.sub(r'^[\d\-\.\s]+', '', line).strip()
                
                # 尝试匹配插件名称
                for plugin_info in plugins_summary:
                    plugin_name = plugin_info['name']
                    plugin_name_lower = plugin_name.lower()
                    line_lower = line.lower()
                    
                    normalized_plugin_name = plugin_name_lower.replace('_', '-')
                    normalized_line = line_lower.replace('_', '-')
                    
                    if (line_lower == plugin_name_lower or 
                        normalized_line == normalized_plugin_name or
                        line_lower in plugin_name_lower or
                        plugin_name_lower in line_lower):
                        if plugin_name not in recommended_plugin_names:
                            recommended_plugin_names.append(plugin_name)
                            break
        
        return recommended_plugin_names

