#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的 AI 客户端
自动从 .env 加载配置，提供简化的调用接口
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dotenv import load_dotenv

from .aiServices.openai import OpenAIClient as OpenAIProvider
from .aiServices.deepseek import DeepSeekClient as DeepSeekProvider


class SimpleAIClient:
    """
    简化的 AI 客户端
    自动处理配置加载、提示词管理等繁琐步骤
    支持多种 AI 服务商，方便扩展
    """
    
    # 服务商注册表
    _providers = {
        'openai': OpenAIProvider,
        'deepseek': DeepSeekProvider,
    }
    
    def __init__(
        self,
        provider: str = 'openai',
        env_file: Optional[Union[str, Path]] = None,
        auto_load_env: bool = True,
        **kwargs
    ):
        """
        初始化简化客户端
        
        Args:
            provider: AI 服务商名称，如 'openai'
            env_file: .env 文件路径，默认为项目根目录的 .env
            auto_load_env: 是否自动加载 .env 文件
            **kwargs: 额外的配置参数（会覆盖 .env 中的配置）
        """
        self.provider_name = provider
        self.env_file = env_file
        self.kwargs = kwargs
        
        # 自动加载环境变量
        if auto_load_env:
            self._load_env()
        
        # 加载服务商配置
        config = self._load_provider_config(provider, **kwargs)
        
        # 初始化服务商客户端
        provider_class = self._get_provider_class(provider)
        self.client = provider_class(**config)
        
        # 提示词模板（可选）
        self.system_prompt = None
        
        # MCP 工具列表（动态管理）
        self.mcp_tools = []
        
        # MCP 工具注册表（用于搜索）
        self.mcp_tool_registry = {}
        
        # 工具路由模式（False=传统模式，True=路由模式）
        self.use_tool_router = False
        
        print(f"[SimpleAIClient] 初始化完成，服务商: {provider}")
    
    def _load_env(self):
        """加载 .env 文件"""
        if self.env_file:
            env_path = Path(self.env_file)
        else:
            # 自动查找项目根目录的 .env 文件
            current = Path(__file__).parent.parent
            env_path = current / '.env'
        
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[SimpleAIClient] 已加载环境变量: {env_path}")
        else:
            print(f"[SimpleAIClient] 警告: 未找到 .env 文件: {env_path}")
    
    def _load_provider_config(self, provider: str, **override_kwargs) -> Dict[str, Any]:
        """
        加载服务商配置
        
        Args:
            provider: 服务商名称
            **override_kwargs: 覆盖配置
            
        Returns:
            配置字典
        """
        config = {}
        
        if provider == 'openai':
            # OpenAI 配置
            config = {
                'api_key': override_kwargs.get('api_key') or os.getenv('OPENAI_API_KEY'),
                'base_url': override_kwargs.get('base_url') or os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                'model': override_kwargs.get('model') or os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                'use_proxy': override_kwargs.get('use_proxy') or (
                    os.getenv('OPENAI_USE_PROXY', 'false').lower() in ('true', '1', 'yes')
                ),
                'proxy_url': override_kwargs.get('proxy_url') or os.getenv('OPENAI_PROXY_URL')
            }
            
            if not config['api_key']:
                raise ValueError("未找到 OPENAI_API_KEY，请在 .env 文件中配置或通过参数传入")
        
        elif provider == 'deepseek':
            # DeepSeek 配置
            config = {
                'api_key': override_kwargs.get('api_key') or os.getenv('DEEPSEEK_API_KEY'),
                'base_url': override_kwargs.get('base_url') or os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
                'model': override_kwargs.get('model') or os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
                'use_proxy': override_kwargs.get('use_proxy') or (
                    os.getenv('DEEPSEEK_USE_PROXY', 'false').lower() in ('true', '1', 'yes')
                ),
                'proxy_url': override_kwargs.get('proxy_url') or os.getenv('DEEPSEEK_PROXY_URL')
            }
            
            if not config['api_key']:
                raise ValueError("未找到 DEEPSEEK_API_KEY，请在 .env 文件中配置或通过参数传入")
        
        else:
            # 其他服务商的配置可以在这里扩展
            raise ValueError(f"不支持的服务商: {provider}，支持的服务商: {list(self._providers.keys())}")
        
        return config
    
    def _get_provider_class(self, provider: str):
        """获取服务商类"""
        if provider not in self._providers:
            raise ValueError(f"未注册的服务商: {provider}，支持的服务商: {list(self._providers.keys())}")
        return self._providers[provider]
    
    def set_system_prompt(self, prompt: Optional[str] = None, inject_mcp_tools: bool = True):
        """
        设置系统提示词
        
        Args:
            prompt: 提示词文本内容（如果为 None，则清除提示词）
            inject_mcp_tools: 是否自动注入 MCP 工具列表到提示词中（默认 True）
        """
        if prompt:
            # 如果需要注入工具列表，替换占位符
            if inject_mcp_tools and self.mcp_tools:
                prompt = self._inject_mcp_tools(prompt)
            self.system_prompt = prompt
        else:
            self.system_prompt = None
            print(f"[SimpleAIClient] 已清除提示词")
    
    def set_mcp_tools(self, tools: List[Dict[str, Any]]):
        """
        设置 MCP 工具列表
        
        Args:
            tools: MCP 工具列表，每个工具包含：
                - name: 工具名称
                - description: 工具描述
                - parameters: 工具参数（可选）
                - 其他工具特定字段
        
        Example:
            tools = [
                {
                    "name": "read_file",
                    "description": "读取文件内容",
                    "parameters": {
                        "path": {"type": "string", "description": "文件路径", "required": True}
                    }
                },
                {
                    "name": "list_directory",
                    "description": "列出目录内容",
                    "parameters": {
                        "path": {"type": "string", "description": "目录路径", "required": True}
                    }
                }
            ]
        """
        self.mcp_tools = tools
        print(f"[SimpleAIClient] 已设置 {len(tools)} 个 MCP 工具")
        
        # 如果已有系统提示词，自动更新
        if self.system_prompt:
            self.system_prompt = self._inject_mcp_tools(self.system_prompt)
            print(f"[SimpleAIClient] 已更新系统提示词中的工具列表")
    
    def add_mcp_tool(self, tool: Dict[str, Any]):
        """
        添加单个 MCP 工具
        
        Args:
            tool: 工具字典，包含 name, description, parameters 等字段
        """
        # 检查是否已存在同名工具
        existing_index = next(
            (i for i, t in enumerate(self.mcp_tools) if t.get('name') == tool.get('name')),
            None
        )
        
        if existing_index is not None:
            # 更新现有工具
            self.mcp_tools[existing_index] = tool
            print(f"[SimpleAIClient] 已更新工具: {tool.get('name')}")
        else:
            # 添加新工具
            self.mcp_tools.append(tool)
            print(f"[SimpleAIClient] 已添加工具: {tool.get('name')}")
        
        # 如果已有系统提示词，自动更新
        if self.system_prompt:
            self.system_prompt = self._inject_mcp_tools(self.system_prompt)
    
    def remove_mcp_tool(self, tool_name: str):
        """
        移除 MCP 工具
        
        Args:
            tool_name: 要移除的工具名称
        """
        self.mcp_tools = [t for t in self.mcp_tools if t.get('name') != tool_name]
        print(f"[SimpleAIClient] 已移除工具: {tool_name}")
        
        # 如果已有系统提示词，自动更新
        if self.system_prompt:
            self.system_prompt = self._inject_mcp_tools(self.system_prompt)
    
    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        获取当前 MCP 工具列表
        
        Returns:
            MCP 工具列表的副本
        """
        return self.mcp_tools.copy()
    
    def register_mcp_tool(self, tool: Dict[str, Any]):
        """
        注册 MCP 工具到注册表（用于搜索，不注入提示词）
        
        Args:
            tool: 工具字典，包含 name, description, parameters, tags 等字段
                - name: 工具名称（必需）
                - description: 工具描述（必需）
                - parameters: 工具参数（可选）
                - tags: 工具标签列表，用于搜索（可选）
                - category: 工具分类（可选）
        """
        if not hasattr(self, 'mcp_tool_registry'):
            self.mcp_tool_registry = {}
        
        tool_name = tool.get('name')
        if not tool_name:
            raise ValueError("工具必须包含 'name' 字段")
        
        # 构建搜索索引
        searchable_tool = {
            'name': tool_name,
            'description': tool.get('description', ''),
            'parameters': tool.get('parameters', {}),
            'tags': tool.get('tags', []),
            'category': tool.get('category', 'general'),
            'full_info': tool  # 保存完整信息
        }
        
        self.mcp_tool_registry[tool_name] = searchable_tool
        print(f"[SimpleAIClient] 已注册工具到注册表: {tool_name}")
    
    def register_mcp_tools(self, tools: List[Dict[str, Any]]):
        """
        批量注册 MCP 工具到注册表
        
        Args:
            tools: 工具列表
        """
        for tool in tools:
            self.register_mcp_tool(tool)
        print(f"[SimpleAIClient] 已批量注册 {len(tools)} 个工具到注册表")
    
    def search_mcp_tools(
        self,
        query: str,
        max_results: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索 MCP 工具（简单文本匹配）
        
        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            category: 工具分类过滤（可选）
            
        Returns:
            匹配的工具列表
        """
        if not hasattr(self, 'mcp_tool_registry'):
            return []
        
        query_lower = query.lower()
        results = []
        
        for tool_name, tool_info in self.mcp_tool_registry.items():
            # 分类过滤
            if category and tool_info.get('category') != category:
                continue
            
            # 搜索匹配（名称、描述、标签）
            score = 0
            if query_lower in tool_name.lower():
                score += 10
            if query_lower in tool_info.get('description', '').lower():
                score += 5
            for tag in tool_info.get('tags', []):
                if query_lower in tag.lower():
                    score += 3
            
            if score > 0:
                results.append({
                    'tool': tool_info['full_info'],
                    'score': score
                })
        
        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # 返回前 N 个结果
        return [r['tool'] for r in results[:max_results]]
    
    def enable_tool_router_mode(self, router_provider: Optional[str] = None):
        """
        启用工具路由模式
        
        在此模式下：
        - 工具不会注入到主提示词中
        - 使用专门的工具路由 AI 来搜索和推荐工具
        - 主 AI 只负责执行工具调用
        
        Args:
            router_provider: 工具路由 AI 的服务商（默认使用主服务商）
        """
        self.use_tool_router = True
        
        # 创建工具路由客户端
        if router_provider:
            router_config = self._load_provider_config(router_provider)
            router_class = self._get_provider_class(router_provider)
            self.tool_router_client = router_class(**router_config)
        else:
            # 使用主服务商创建一个新实例（避免历史混淆）
            router_config = self._load_provider_config(self.provider_name)
            router_class = self._get_provider_class(self.provider_name)
            self.tool_router_client = router_class(**router_config)
        
        print(f"[SimpleAIClient] 已启用工具路由模式")
    
    def find_tools_for_task(self, task_description: str, mcp_registry=None, max_tools: int = 1) -> Dict[str, Any]:
        """
        使用工具路由 AI 查找适合任务的 MCP 工具插件
        
        Args:
            task_description: 任务描述
            mcp_registry: MCPRegistry 实例，用于获取插件列表
            max_tools: 最大返回插件数（通常为1）
            
        Returns:
            包含插件列表和状态的字典，格式: {
                'success': bool,
                'plugins': List[Dict],  # 推荐的插件列表（包含插件名称和描述）
                'message': str,       # 状态消息
                'ai_response': str    # AI 的原始响应（如果成功）
            }
        """
        # 检查是否启用了路由模式
        if not self.use_tool_router or not self.tool_router_client:
            return {
                'success': False,
                'plugins': [],
                'message': '工具路由模式未启用，请先调用 enable_tool_router_mode()',
                'ai_response': None
            }
        
        # 检查是否有 MCP Registry
        if not mcp_registry:
            return {
                'success': False,
                'plugins': [],
                'message': '需要提供 MCPRegistry 实例',
                'ai_response': None
            }
        
        # 获取所有插件信息（从 manifest.json）
        plugins_summary = []
        for plugin_name, plugin_info in mcp_registry.plugins.items():
            manifest = plugin_info.get('manifest', {})
            plugins_summary.append({
                'name': plugin_name,
                'description': manifest.get('description', ''),
            })
        
        if not plugins_summary:
            return {
                'success': False,
                'plugins': [],
                'message': '没有可用的 MCP 工具插件',
                'ai_response': None
            }
        
        # 格式化插件列表
        plugins_text = "\n".join([
            f"- {p['name']}: {p['description']}"
            for p in plugins_summary
        ])
        
        # 构建搜索请求
        search_prompt = f"""用户任务: {task_description}

请从上述插件列表中选择最合适的插件。"""
        
        # 加载工具路由提示词（必须从文件读取）
        try:
            router_prompt = self.load_prompt_from_file('prompts/mcp_tool_router.txt')
            # 注入插件列表
            router_prompt = router_prompt.replace('{MCP_PLUGINS}', plugins_text)
        except FileNotFoundError as e:
            return {
                'success': False,
                'plugins': [],
                'message': f'无法加载工具路由提示词文件: {str(e)}',
                'ai_response': None
            }
        
        # 调用工具路由 AI
        try:
            response = self.tool_router_client.chat(
                messages=[
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": search_prompt}
                ],
                max_tokens=200,
                use_history=False
            )
        except Exception as e:
            return {
                'success': False,
                'plugins': [],
                'message': f'工具路由 AI 调用失败: {str(e)}',
                'ai_response': None
            }
        
        # 检查 AI 调用是否成功
        if not response.get('success'):
            return {
                'success': False,
                'plugins': [],
                'message': f"工具路由 AI 返回错误: {response.get('message', '未知错误')}",
                'ai_response': None
            }
        
        ai_response = response.get('content', '').strip()
        
        # 检查是否未找到工具
        if '未找到' in ai_response or '没有找到' in ai_response or 'no match' in ai_response.lower():
            return {
                'success': False,
                'plugins': [],
                'message': 'AI 未找到匹配的插件',
                'ai_response': ai_response
            }
        
        # 从响应中提取推荐的插件名称
        recommended_plugin_names = []
        ai_response_lower = ai_response.lower().strip()
        import re
        
        # 方法1: 精确匹配插件名称（支持连字符和下划线互换）
        for plugin_info in plugins_summary:
            plugin_name = plugin_info['name']
            plugin_name_lower = plugin_name.lower()
            
            # 检查响应中是否包含插件名称（支持连字符和下划线互换）
            # 例如：web_douyin 可以匹配 web-douyin 或 web_douyin
            normalized_plugin_name = plugin_name_lower.replace('_', '-')
            normalized_response = ai_response_lower.replace('_', '-')
            
            # 尝试匹配原始名称
            pattern1 = r'\b' + re.escape(plugin_name_lower) + r'\b'
            # 尝试匹配连字符版本（如果原名称是下划线）
            pattern2 = r'\b' + re.escape(normalized_plugin_name) + r'\b'
            
            if re.search(pattern1, ai_response_lower) or re.search(pattern2, normalized_response):
                if plugin_name not in recommended_plugin_names:
                    recommended_plugin_names.append(plugin_name)
        
        # 方法2: 如果方法1没找到，尝试逐行提取（支持每行一个插件名称）
        if not recommended_plugin_names:
            lines = ai_response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 移除可能的编号前缀（如 "1. " 或 "- "）
                line = re.sub(r'^[\d\-\.\s]+', '', line).strip()
                
                # 尝试匹配插件名称（支持连字符和下划线互换）
                for plugin_info in plugins_summary:
                    plugin_name = plugin_info['name']
                    plugin_name_lower = plugin_name.lower()
                    line_lower = line.lower()
                    
                    # 检查是否完全匹配（支持连字符和下划线互换）
                    normalized_plugin_name = plugin_name_lower.replace('_', '-')
                    normalized_line = line_lower.replace('_', '-')
                    
                    if (line_lower == plugin_name_lower or 
                        normalized_line == normalized_plugin_name or
                        line_lower in plugin_name_lower or
                        plugin_name_lower in line_lower):
                        if plugin_name not in recommended_plugin_names:
                            recommended_plugin_names.append(plugin_name)
                            break
        
        # 如果没有提取到插件名称
        if not recommended_plugin_names:
            return {
                'success': False,
                'plugins': [],
                'message': '无法从 AI 响应中提取插件名称',
                'ai_response': ai_response
            }
        
        # 返回插件信息
        result_plugins = []
        for plugin_name in recommended_plugin_names[:max_tools]:
            if plugin_name in mcp_registry.plugins:
                plugin_info = mcp_registry.plugins[plugin_name]
                result_plugins.append({
                    'name': plugin_name,
                    'description': plugin_info.get('manifest', {}).get('description', ''),
                    'plugin_info': plugin_info
                })
        
        # 如果提取到的插件名称在注册表中找不到
        if not result_plugins:
            return {
                'success': False,
                'plugins': [],
                'message': f'AI 推荐的插件在注册表中不存在: {recommended_plugin_names}',
                'ai_response': ai_response
            }
        
        return {
            'success': True,
            'plugins': result_plugins,
            'message': f'成功找到 {len(result_plugins)} 个推荐插件',
            'ai_response': ai_response
        }
    
    def _format_tools_summary(self, tools_summary: List[Dict[str, Any]]) -> str:
        """格式化工具摘要"""
        lines = []
        for i, tool in enumerate(tools_summary, 1):
            lines.append(f"{i}. {tool['name']} ({tool.get('category', 'general')})")
            lines.append(f"   {tool['description']}")
            lines.append("")
        return "\n".join(lines)
    
    def _extract_tool_names_from_response(self, response: str, tools_summary: List[Dict[str, Any]]) -> List[str]:
        """
        从 AI 响应中提取工具名称
        
        支持多种格式：
        1. 单独工具名称：todo.list
        2. 逗号分隔：工具1, 工具2, 工具3
        3. 编号列表：1. 工具1\n2. 工具2
        4. 自然语言中提到工具名称
        """
        import re
        tool_names = []
        response_lower = response.lower().strip()
        
        # 获取所有可用工具名称（用于精确匹配）
        available_tools = {tool['name'].lower(): tool['name'] for tool in tools_summary}
        
        # 方法1: 精确匹配完整工具名称（优先）
        # 检查响应中是否包含完整的工具名称
        for tool_lower, tool_original in available_tools.items():
            # 使用单词边界或行边界匹配，确保匹配完整工具名称
            # 匹配模式：行首/空格/逗号 + 工具名称 + 行尾/空格/逗号
            pattern = r'(?:^|[\s,\n])' + re.escape(tool_lower) + r'(?:[\s,\n]|$)'
            if re.search(pattern, response_lower):
                if tool_original not in tool_names:
                    tool_names.append(tool_original)
        
        # 如果方法1找到了，直接返回
        if tool_names:
            return tool_names
        
        # 方法2: 尝试提取逗号分隔的工具列表
        # 查找类似 "工具1, 工具2, 工具3" 的格式
        comma_pattern = r'([a-z_][a-z0-9_.]*(?:\s*,\s*[a-z_][a-z0-9_.]*)*)'
        comma_matches = re.findall(comma_pattern, response_lower)
        
        if comma_matches:
            # 取最长的匹配（通常是工具列表）
            longest_match = max(comma_matches, key=len)
            potential_tools = [t.strip() for t in longest_match.split(',')]
            
            # 验证这些是否是有效的工具名称（必须完全匹配）
            for tool in tools_summary:
                tool_name_lower = tool['name'].lower()
                for potential in potential_tools:
                    # 只接受完全匹配，不接受部分匹配
                    if potential == tool_name_lower:
                        if tool['name'] not in tool_names:
                            tool_names.append(tool['name'])
        
        # 方法3: 从工具摘要中查找提到的工具（如果前面方法都没找到）
        if not tool_names:
            for tool in tools_summary:
                tool_name = tool['name'].lower()
                # 检查工具名称是否在响应中被明确提到
                # 使用单词边界匹配，避免部分匹配
                pattern = r'\b' + re.escape(tool_name) + r'\b'
                if re.search(pattern, response_lower):
                    if tool['name'] not in tool_names:
                        tool_names.append(tool['name'])
        
        # 方法4: 尝试从编号列表中提取（如 "1. todo.list"）
        if not tool_names:
            numbered_pattern = r'\d+[\.、]\s*([a-z_][a-z0-9_.]+)'
            numbered_matches = re.findall(numbered_pattern, response_lower)
            for match in numbered_matches:
                for tool in tools_summary:
                    if tool['name'].lower() == match:
                        if tool['name'] not in tool_names:
                            tool_names.append(tool['name'])
        
        return tool_names
    
    def _inject_mcp_tools(self, prompt: str) -> str:
        """
        将 MCP 工具列表注入到提示词中
        
        Args:
            prompt: 原始提示词
            
        Returns:
            注入工具列表后的提示词
        """
        if not self.mcp_tools:
            # 如果没有工具，移除占位符或返回原提示词
            return prompt.replace('{MCP_TOOLS}', '当前没有可用的 MCP 工具。')
        
        # 格式化工具列表
        tools_text = self._format_mcp_tools()
        
        # 替换占位符
        if '{MCP_TOOLS}' in prompt:
            return prompt.replace('{MCP_TOOLS}', tools_text)
        else:
            # 如果没有占位符，追加到提示词末尾
            return f"{prompt}\n\n## 当前可用的 MCP 工具\n\n{tools_text}"
    
    def _format_mcp_tools(self) -> str:
        """
        格式化 MCP 工具列表为文本
        
        Returns:
            格式化后的工具列表文本
        """
        if not self.mcp_tools:
            return "当前没有可用的 MCP 工具。"
        
        lines = []
        for i, tool in enumerate(self.mcp_tools, 1):
            name = tool.get('name', '未知工具')
            description = tool.get('description', '无描述')
            
            lines.append(f"### {i}. {name}")
            lines.append(f"**描述**: {description}")
            
            # 参数信息
            parameters = tool.get('parameters', {})
            if parameters:
                lines.append("**参数**:")
                if isinstance(parameters, dict):
                    for param_name, param_info in parameters.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'unknown')
                            param_desc = param_info.get('description', '无描述')
                            required = param_info.get('required', False)
                            required_text = "（必填）" if required else "（可选）"
                            lines.append(f"  - `{param_name}` ({param_type}): {param_desc} {required_text}")
                        else:
                            lines.append(f"  - `{param_name}`: {param_info}")
                else:
                    lines.append(f"  {parameters}")
            
            # 其他工具特定信息
            for key, value in tool.items():
                if key not in ('name', 'description', 'parameters'):
                    lines.append(f"**{key}**: {value}")
            
            lines.append("")  # 空行分隔
        
        return "\n".join(lines)
    
    def load_prompt_from_file(self, prompt_file: Union[str, Path]) -> str:
        """
        从文件加载提示词内容（不设置，只返回内容）
        
        Args:
            prompt_file: 提示词文件路径
            
        Returns:
            提示词文本内容
        """
        prompt_path = Path(prompt_file)
        if not prompt_path.is_absolute():
            # 如果是相对路径，尝试从项目根目录查找
            project_root = Path(__file__).parent.parent
            prompt_path = project_root / prompt_path
        
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            return content
        else:
            raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")
    
    def chat(
        self,
        content: Union[str, List[Dict[str, str]]],
        system_prompt: Optional[str] = None,
        use_history: bool = True,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        简化的对话接口
        
        Args:
            content: 用户消息内容（字符串）或消息列表
            system_prompt: 系统提示词（可选，会覆盖已设置的提示词）
            use_history: 是否使用历史对话
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            包含响应内容的字典，格式: {
                'success': bool,
                'content': str,  # AI 回复内容
                'usage': dict,   # Token 使用情况
                'cost': dict,    # 费用信息（如果有）
                'model': str     # 使用的模型
            }
        """
        # 构建消息列表
        messages = []
        
        # 系统提示词优先级：参数 > 已设置的 > None
        final_system_prompt = system_prompt or self.system_prompt
        if final_system_prompt:
            messages.append({
                "role": "system",
                "content": final_system_prompt
            })
        
        # 用户消息
        if isinstance(content, str):
            messages.append({
                "role": "user",
                "content": content
            })
        elif isinstance(content, list):
            messages.extend(content)
        else:
            raise ValueError("content 必须是字符串或消息列表")
        
        # 调用服务商客户端
        if self.provider_name == 'openai':
            response = self.client.chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                use_history=use_history,
                **kwargs
            )
        elif self.provider_name == 'deepseek':
            response = self.client.chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                use_history=use_history,
                **kwargs
            )
        else:
            # 其他服务商的调用逻辑可以在这里扩展
            raise ValueError(f"暂不支持的服务商: {self.provider_name}")
        
        return response
    
    def chat_with_image(
        self,
        image_path: str,
        text_prompt: str = "",
        system_prompt: Optional[str] = None,
        use_history: bool = True,
        max_tokens: int = 500,
        temperature: float = 0.7,
        image_detail: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        图片对话接口
        
        Args:
            image_path: 图片文件路径
            text_prompt: 文本提示词
            system_prompt: 系统提示词（可选）
            use_history: 是否使用历史对话
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            image_detail: 图片细节级别
            **kwargs: 其他参数
            
        Returns:
            响应字典
        """
        if self.provider_name in ['openai', 'deepseek']:
            final_system_prompt = system_prompt or self.system_prompt
            response = self.client.chat_with_image(
                image_path=image_path,
                text_prompt=text_prompt,
                system_prompt=final_system_prompt,
                use_history=use_history,
                max_tokens=max_tokens,
                temperature=temperature,
                image_detail=image_detail,
                **kwargs
            )
        else:
            raise ValueError(f"暂不支持的服务商: {self.provider_name}")
        
        return response
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        if hasattr(self.client, 'get_conversation_history'):
            return self.client.get_conversation_history()
        return []
    
    def clear_history(self):
        """清空对话历史"""
        if hasattr(self.client, 'clear_conversation_history'):
            self.client.clear_conversation_history()
    
    @classmethod
    def register_provider(cls, name: str, provider_class):
        """
        注册新的 AI 服务商
        
        Args:
            name: 服务商名称
            provider_class: 服务商客户端类
        """
        cls._providers[name] = provider_class
        print(f"[SimpleAIClient] 已注册服务商: {name}")
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有已注册的服务商"""
        return list(cls._providers.keys())

