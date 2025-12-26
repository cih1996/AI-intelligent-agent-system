#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的 AI 客户端
自动从 .env 加载配置，提供简化的调用接口
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable
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
        name: Optional[str] = None,
        prompt_file: Optional[Union[str, Path]] = None,
        history_file: Optional[Union[str, Path]] = None,
        stream_callback: Optional[Callable[[Dict[str, Any], str], None]] = None,
        **kwargs
    ):
        """
        初始化简化客户端
        
        Args:
            provider: AI 服务商名称，如 'openai'
            env_file: .env 文件路径，默认为项目根目录的 .env
            auto_load_env: 是否自动加载 .env 文件
            name: Agent 名称（用于日志文件/历史对话命名，可选）
            prompt_file: 提示词文件路径（可选）
            history_file: 历史对话文件路径（可选，如果不提供则自动生成）
            stream_callback: 传输回调函数
            **kwargs: 额外的配置参数（会覆盖 .env 中的配置）
                - enable_auto_compress: 是否启用自动上下文压缩（默认 False）
                - compress_token_threshold: token阈值，达到此值触发压缩（默认 10000）
                - compress_turn_threshold: 轮次阈值，达到此值触发压缩（默认 20，每轮包含user+assistant两条消息）
                - compressor_prompt_file: 压缩AI的提示词文件路径（默认 'prompts/mcp_context_compressor.txt'）
        """
        self.provider_name = provider
        self.env_file = env_file
        self.stream_callback = stream_callback
        self.kwargs = kwargs
        self.name = name
        self.log_dir = "logs"
        # history_dir 将在 _init_history_file 中根据 history_file 参数设置
        self.history_dir = None
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
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
        self._original_system_prompt = None  # 保存原始系统提示词模板
        
        # MCP 工具列表（动态管理）
        self.mcp_tools = []
        
        # MCP 工具注册表（用于搜索）
        self.mcp_tool_registry = {}
        
        # 工具路由模式（False=传统模式，True=路由模式）
        self.use_tool_router = False
        
        # 内部历史对话管理（不包含系统提示词）
        self._conversation_history = []
        
        # 上下文压缩配置
        self.enable_auto_compress = kwargs.get('enable_auto_compress', False)
        self.compress_token_threshold = kwargs.get('compress_token_threshold', 10000)  # token阈值
        self.compress_turn_threshold = kwargs.get('compress_turn_threshold', 20)  # 轮次阈值
        self.compressor_prompt_file = kwargs.get('compressor_prompt_file', 'prompts/mcp_context_compressor.txt')
        self._compressor_client = None  # 延迟初始化压缩AI客户端
        self._is_compressing = False  # 防止递归压缩的标志位
        self._context_summary_placeholder = '{CONTEXT_SUMMARY}'  # 上下文总结占位符
        self._context_summary = None  # 当前保存的上下文总结内容
        
        # 初始化日志文件（如果提供了 name）
        self.log_file = None
        if name:
            self.log_file = self._init_log_file()
        
        # 加载并设置系统提示词（如果提供了 prompt_file）
        if prompt_file:
            self.prompt_file = prompt_file
            self.system_prompt = self._load_system_prompt()
            self._original_system_prompt = self.system_prompt  # 保存原始模板
            self.set_system_prompt(self.system_prompt, inject_mcp_tools=False)
            if self.log_file:
                self.log_interaction("system", self.system_prompt, is_system=True)
        
        # 初始化历史对话文件
        self.history_file = self._init_history_file(history_file)
        
        # 加载历史对话（如果文件存在）
        if self.history_file and os.path.exists(self.history_file):
            self._load_history()
        
        # 加载上下文总结（如果文件存在，无论是否启用自动压缩都要加载）
        # 因为总结可能已经存在，需要在 update_system_prompt 时使用
        self._load_context_summary()
 
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
    
    def _init_log_file(self) -> Optional[str]:
        """
        初始化日志文件
        
        Returns:
            日志文件路径，如果未提供 name 则返回 None
        """
        if not self.name:
            return None
        
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 生成日志文件名（包含时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{self.name.lower()}_{timestamp}.log"
        log_path = os.path.join(self.log_dir, log_filename)
        
        # 写入初始日志
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"=== {self.name} 对话日志 ===\n")
            f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"服务商: {self.provider_name}\n")
            f.write(f"{'='*80}\n\n")
    
        return log_path
    
    def _load_system_prompt(self) -> str:
        """
        从文件加载系统提示词
        
        Returns:
            提示词内容
        """
        if not hasattr(self, 'prompt_file') or not self.prompt_file:
            return ""
        
        try:
            prompt_path = Path(self.prompt_file)
            if not prompt_path.is_absolute():
                # 如果是相对路径，从项目根目录查找
                project_root = Path(__file__).parent.parent
                prompt_path = project_root / prompt_path
            
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                return content
            else:
                raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")
        except Exception as e:
            name = self.name or "SimpleAIClient"
            print(f"⚠ [{name}] 加载提示词失败: {e}")
            return ""
    
    def _init_history_file(self, history_file: Optional[Union[str, Path]]) -> Optional[str]:
        """
        初始化历史对话文件
        
        Args:
            history_file: 会话目录名（可选），用于构建路径 conversations/[history_file]/[AI名称].session
            
        Returns:
            历史对话文件路径，如果未提供则自动生成
        """
        project_root = Path(__file__).parent.parent
        
        # 确定会话目录名
        if history_file:
            # 使用提供的会话目录名
            session_dir_name = str(history_file)
        else:
            # 如果未提供，使用默认会话目录名
            session_dir_name = "default"
        
        # 构建历史对话目录路径：conversations/[history_file]/
        self.history_dir = project_root / "conversations" / session_dir_name
        os.makedirs(self.history_dir, exist_ok=True)
        
        # 构建历史对话文件路径：conversations/[history_file]/[AI名称].session
        if self.name:
            # 使用 AI 名称生成文件名
            filename = f"{self.name.lower().replace(' ', '_')}.session"
        else:
            # 如果没有名称，使用时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_{timestamp}.session"
        
        history_path = self.history_dir / filename
        return str(history_path)
    
    def _load_history(self):
        """
        从文件加载历史对话（不包含系统提示词）
        """
        if not self.history_file or not os.path.exists(self.history_file):
            return
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            # 确保是列表格式
            if isinstance(history_data, list):
                # 过滤掉系统提示词
                filtered_history = [
                    msg for msg in history_data 
                    if msg.get('role') != 'system'
                ]
                
                # 加载到内部历史记录中
                self._conversation_history = filtered_history
            
            name = self.name or "SimpleAIClient"
            print(f"✓ [{name}] 已加载历史对话: {len(filtered_history)} 条消息")
        except Exception as e:
            name = self.name or "SimpleAIClient"
            print(f"⚠ [{name}] 加载历史对话失败: {e}")
    
    def _save_history(self):
        """
        保存历史对话到文件（不包含系统提示词）
        """
        if not self.history_file:
            return
        
        try:
            # 保存内部历史对话到文件
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._conversation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            name = self.name or "SimpleAIClient"
            print(f"⚠ [{name}] 保存历史对话失败: {e}")
    
    def log_interaction(
        self,
        role: str,
        content: str,
        is_system: bool = False
    ):
        """
        记录对话交互日志
        
        Args:
            role: 角色（system/user/assistant）
            content: 内容
            is_system: 是否为系统提示词（避免重复记录）
        """
        if not self.log_file:
            return
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"【{self.name}】- {role.upper()}\n")
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*80}\n")
                f.write(f"{content}\n")
                f.write(f"{'='*80}\n\n")
        except Exception as e:
            print(f"⚠ [{self.name}] 日志记录失败: {e}")
    

    def update_system_prompt(
        self, 
        replacements: Dict[str, str],
        log_update: bool = False
    ):
        """
        更新系统提示词（仅支持变量替换）

        使用方式：
        必须提供替换字典: update_system_prompt(replacements={'{USER_MEMORY}': '内容'})

        Args:
            replacements: 替换字典，格式: {'占位符': '替换内容'}
                例如: {'{USER_MEMORY}': '用户记忆内容', '{MCP_TOOLS}': '工具列表'}
            log_update: 是否记录到日志（默认 False，避免重复写入大量系统提示词）
        """
        if not replacements or not isinstance(replacements, dict):
            raise ValueError("必须提供 replacements 参数，并且为字典类型")
        
        if not self._original_system_prompt:
            # 如果没有原始模板，使用当前的系统提示词作为模板
            self._original_system_prompt = self.system_prompt or ""

        # 确保总结已加载（如果还没加载，尝试加载）
        # 这确保第一次调用 update_system_prompt 时也能加载历史总结
        if self._context_summary is None and self.history_file:
            self._load_context_summary()

        # 从原始模板开始替换
        updated_prompt = self._original_system_prompt
        
        # 执行所有替换
        for placeholder, value in replacements.items():
            updated_prompt = updated_prompt.replace(placeholder, value)

        # 如果有保存的上下文总结，确保总结被注入
        if self._context_summary:
            if self._context_summary_placeholder in updated_prompt:
                # 如果模板中有占位符，替换占位符
                updated_prompt = updated_prompt.replace(
                    self._context_summary_placeholder,
                    self._context_summary
                )
            else:
                # 如果模板中没有占位符，追加到末尾
                # 但需要检查是否已经包含总结（避免重复追加）
                if "## 历史对话总结" not in updated_prompt:
                    updated_prompt = f"{updated_prompt}\n\n## 历史对话总结\n\n{self._context_summary}"
        
        # 更新系统提示词
        self.system_prompt = updated_prompt
        self.set_system_prompt(updated_prompt, inject_mcp_tools=False)
        # 只有在明确要求时才记录到日志
        if log_update and self.log_file:
            self.log_interaction("system", "[系统提示词已更新]", is_system=True)
    
    def get_default_context(self) -> str:
        """
        生成每次对话默认必带的信息（如当前时间）

        Returns:
            str: 格式化的包含当前时间/日期/星期的字符串
        """
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_weekday = datetime.now().strftime("%A")
        return f"[当前时间: {current_time} ({current_date} {current_weekday})]\n\n"
    
    def _get_compressor_client(self) -> Optional['SimpleAIClient']:
        """
        获取或创建压缩AI客户端（延迟初始化）
        
        Returns:
            压缩AI客户端实例，如果压缩功能未启用则返回 None
        """
        if not self.enable_auto_compress:
            return None
        
        if self._compressor_client is None:
            # 延迟初始化压缩AI客户端
            # 使用相同的provider，但不使用历史记录，避免递归压缩
            self._compressor_client = SimpleAIClient(
                provider=self.provider_name,
                name=f"{self.name}_压缩AI" if self.name else "压缩AI",
                prompt_file=self.compressor_prompt_file,
                enable_auto_compress=False,  # 压缩AI本身不启用压缩，防止递归
                **self.kwargs
            )
            print(f"✓ [{self.name or 'SimpleAIClient'}] 已初始化压缩AI客户端")
        
        return self._compressor_client
    
    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        估算消息列表的token数量（简单估算：中文约1.5字符=1token，英文约4字符=1token）
        
        Args:
            messages: 消息列表
            
        Returns:
            估算的token数量
        """
        total_chars = 0
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                total_chars += len(content)
        
        # 简单估算：混合中英文，平均约2字符=1token
        # 加上消息格式的开销（role等），乘以1.2作为缓冲
        estimated_tokens = int(total_chars / 2 * 1.2)
        return estimated_tokens
    
    def _truncate_long_messages(self, messages: List[Dict[str, str]], max_tokens_per_message: int = 2000):
        """
        截断超长的消息内容
        
        Args:
            messages: 消息列表（会被原地修改）
            max_tokens_per_message: 单条消息的最大token数（默认2000）
        """
        max_chars_per_message = max_tokens_per_message * 2  # 字符数约等于token数*2
        
        for i, msg in enumerate(messages):
            content = msg.get('content', '')
            if not isinstance(content, str):
                continue
            
            # 估算当前消息的token数
            msg_tokens = self._estimate_tokens([msg])
            
            if msg_tokens > max_tokens_per_message and len(content) > max_chars_per_message:
                # 如果消息超长，截断内容（保留开头和结尾）
                # 保留前40%和后40%，中间用省略标记
                keep_chars = int(max_chars_per_message * 0.4)
                
                truncated_content = (
                    content[:keep_chars] + 
                    "\n\n[... 内容过长已截断（保留开头和结尾）...]\n\n" + 
                    content[-keep_chars:]
                )
                
                messages[i]['content'] = truncated_content
                name = self.name or "SimpleAIClient"
                print(f"⚠ [{name}] 消息过长已截断: {msg_tokens} tokens → 约 {max_tokens_per_message} tokens")
    
    def _should_compress(self) -> bool:
        """
        判断是否需要压缩历史上下文
        
        Returns:
            如果需要压缩返回 True，否则返回 False
        """
        if not self.enable_auto_compress:
            return False
        
        if self._is_compressing:
            # 正在压缩中，不触发新的压缩
            return False
        
        # 检查轮次阈值
        if len(self._conversation_history) >= self.compress_turn_threshold * 2:
            # 轮次阈值：每轮对话包含user和assistant两条消息
            return True
        
        # 检查token阈值
        if self._conversation_history:
            estimated_tokens = self._estimate_tokens(self._conversation_history)
            if estimated_tokens >= self.compress_token_threshold:
                return True
        
        return False
    
    def _compress_context(self) -> Optional[str]:
        """
        压缩历史上下文
        
        Returns:
            压缩后的总结文本，如果压缩失败返回 None
        """
        if not self.enable_auto_compress or self._is_compressing:
            return None
        
        if not self._conversation_history:
            return None
        
        compressor = self._get_compressor_client()
        if not compressor:
            return None
        
        try:
            self._is_compressing = True
            
            # 构建压缩请求
            history_json = json.dumps(self._conversation_history, ensure_ascii=False, indent=2)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            compress_input = (
                f"请压缩以下历史对话上下文：\n\n"
                f"当前时间：{current_time}\n\n"
                f"历史对话上下文（JSON格式）：\n{history_json}\n\n"
                f"请生成适合注入到系统提示词中的总结。"
            )
            
            # 调用压缩AI（不使用历史记录，避免递归）
            response = compressor.chat(
                content=compress_input,
                use_history=False,
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.get("success"):
                summary = response.get("content", "").strip()
                if summary:
                    name = self.name or "SimpleAIClient"
                    print(f"✓ [{name}] 上下文压缩完成，总结长度: {len(summary)} 字符")
                    return summary
                else:
                    print(f"⚠ [{self.name or 'SimpleAIClient'}] 压缩AI返回空总结")
            else:
                error_msg = response.get('message', '未知错误')
                print(f"⚠ [{self.name or 'SimpleAIClient'}] 压缩AI调用失败: {error_msg}")
        
        except Exception as e:
            name = self.name or "SimpleAIClient"
            print(f"⚠ [{name}] 压缩上下文时出错: {e}")
        
        finally:
            self._is_compressing = False
        
        return None
    
    def _get_context_summary_file(self) -> Optional[str]:
        """
        获取上下文总结文件路径
        
        Returns:
            总结文件路径，如果未设置则返回 None
        """
        if not self.name or not self.history_file:
            return None
        
        # 总结文件与历史对话文件在同一目录，文件名添加 _summary 后缀
        history_path = Path(self.history_file)
        summary_path = history_path.parent / f"{history_path.stem}_summary.txt"
        return str(summary_path)
    
    def _save_context_summary(self, summary: str):
        """
        保存上下文总结到文件
        
        Args:
            summary: 总结文本
        """
        if not summary:
            return
        
        summary_file = self._get_context_summary_file()
        if not summary_file:
            return
        
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            name = self.name or "SimpleAIClient"
            print(f"✓ [{name}] 已保存上下文总结到文件: {summary_file}")
        except Exception as e:
            name = self.name or "SimpleAIClient"
            print(f"⚠ [{name}] 保存上下文总结失败: {e}")
    
    def _load_context_summary(self) -> Optional[str]:
        """
        从文件加载上下文总结
        
        Returns:
            总结文本，如果文件不存在或加载失败返回 None
        """
        summary_file = self._get_context_summary_file()
        if not summary_file or not os.path.exists(summary_file):
            return None
        
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = f.read().strip()
            
            if summary:
                self._context_summary = summary
                name = self.name or "SimpleAIClient"
                print(f"✓ [{name}] 已加载上下文总结: {len(summary)} 字符")
                return summary
        except Exception as e:
            name = self.name or "SimpleAIClient"
            print(f"⚠ [{name}] 加载上下文总结失败: {e}")
        
        return None
    
    def _inject_context_summary(self, summary: str, save_to_file: bool = True):
        """
        将上下文总结注入到系统提示词中
        
        Args:
            summary: 压缩后的总结文本
            save_to_file: 是否保存到文件（默认 True）
        """
        if not summary:
            return
        
        # 保存总结内容到内存
        self._context_summary = summary
        
        # 保存到文件
        if save_to_file:
            self._save_context_summary(summary)
        
        # 如果原始系统提示词中有占位符，替换占位符
        if self._original_system_prompt:
            if self._context_summary_placeholder in self._original_system_prompt:
                # 替换占位符
                updated_prompt = self._original_system_prompt.replace(
                    self._context_summary_placeholder,
                    summary
                )
            else:
                # 如果没有占位符，追加到末尾
                updated_prompt = f"{self._original_system_prompt}\n\n## 历史对话总结\n\n{summary}"
            
            # 更新系统提示词（不自动注入MCP工具，保持当前状态）
            self.system_prompt = updated_prompt
            # 如果启用了MCP工具注入，需要重新注入
            if self.mcp_tools:
                self.system_prompt = self._inject_mcp_tools(self.system_prompt)
            
            name = self.name or "SimpleAIClient"
            print(f"✓ [{name}] 已注入上下文总结到系统提示词")

    def chat(
        self,
        content: Union[str, List[Dict[str, str]]],
        system_prompt: Optional[str] = None,
        use_history: bool = True,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None,
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
            stream: 是否开启流式传输，默认 False
            stream_options: 流式输出相关选项，字典格式，包含 include_usage (bool)
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
        # 记录用户输入（如果是字符串）
        if isinstance(content, str) and self.log_file:
            self.log_interaction("user", content)
        elif isinstance(content, list) and self.log_file:
            # 记录所有非系统消息
            for msg in content:
                role = msg.get('role', 'unknown')
                msg_content = msg.get('content', '')
                if role != 'system':
                    self.log_interaction(role, msg_content)
        
        # 如果开启了流式传输，创建包装的回调函数
        wrapped_callback = None
        if stream and self.stream_callback:
            def _wrapped_callback(chunk_data: Dict[str, Any], accumulated_content: str):
                # 先调用用户提供的回调
                try:
                    self.stream_callback(self.name,chunk_data, accumulated_content)
                except Exception as e:
                    name = self.name or "SimpleAIClient"
                    print(f"⚠ [{name}] 回调函数执行出错: {e}")
            
            wrapped_callback = _wrapped_callback
        
        # 构建完整的消息列表（系统提示词 + 历史对话 + 当前消息）
        full_messages = []
        
        # 1. 添加系统提示词（优先级：参数 > 已设置的 > None）
        final_system_prompt = system_prompt or self.system_prompt
        if final_system_prompt:
            full_messages.append({
                "role": "system",
                "content": final_system_prompt
            })
        
        # 2. 检查是否需要压缩历史上下文（在添加历史之前检查）
        if use_history and self._should_compress():
            summary = self._compress_context()
            if summary:
                # 注入总结到系统提示词
                self._inject_context_summary(summary)
                # 清空历史对话（保留最近几轮，避免完全清空）
                # 保留最近2轮对话（4条消息：user + assistant）
                keep_recent = min(4, len(self._conversation_history))
                if keep_recent > 0:
                    self._conversation_history = self._conversation_history[-keep_recent:]
                    # 检查保留的消息是否超长token，如果超长则截断
                    self._truncate_long_messages(self._conversation_history)
                else:
                    self._conversation_history = []
                # 保存更新后的历史到持久化文件
                if self.history_file:
                    self._save_history()
                name = self.name or "SimpleAIClient"
                print(f"✓ [{name}] 已压缩并清空历史上下文，保留最近 {keep_recent} 条消息，已保存到文件")
        
        # 2. 添加历史对话（如果启用）
        if use_history:
            full_messages.extend(self._conversation_history.copy())
            
        content = self.get_default_context() + content
        # 3. 添加当前用户消息
        if isinstance(content, str):
            user_message = {
                "role": "user",
                "content": content
            }
            full_messages.append(user_message)
        elif isinstance(content, list):
            full_messages.extend(content)
        else:
            raise ValueError("content 必须是字符串或消息列表")
        
        # 调用服务商客户端（传入完整的消息列表）
        if self.provider_name == 'openai':
            response = self.client.chat(
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        elif self.provider_name == 'deepseek':
            response = self.client.chat(
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                stream_options=stream_options,
                callback=wrapped_callback,
                **kwargs
            )
        else:
            # 其他服务商的调用逻辑可以在这里扩展
            raise ValueError(f"暂不支持的服务商: {self.provider_name}")
        
        # 记录 AI 回复（流式传输完成后会包含完整内容）
        if self.log_file:
            if response.get("success"):
                ai_content = response.get("content", "")
                self.log_interaction("assistant", ai_content)
            else:
                error_msg = response.get('message', '未知错误')
                self.log_interaction("assistant", f"[错误] {error_msg}")
        
        # 如果对话成功，更新内部历史记录并保存到文件
        if response.get("success") and use_history:
            # 添加用户消息到历史（如果是字符串）
            if isinstance(content, str):
                self._conversation_history.append({
                    "role": "user",
                    "content": content
                })
            elif isinstance(content, list):
                # 如果是消息列表，添加所有非系统消息
                for msg in content:
                    if msg.get('role') != 'system':
                        self._conversation_history.append(msg.copy())
            
            # 添加AI回复到历史
            ai_content = response.get("content", "")
            if ai_content:
                self._conversation_history.append({
                    "role": "assistant",
                    "content": ai_content
                })
            
            # 保存到文件
            if self.history_file:
                self._save_history()
        
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
            # 构建完整的消息列表（系统提示词 + 历史对话）
            full_messages = []
            
            # 1. 添加系统提示词
            final_system_prompt = system_prompt or self.system_prompt
            if final_system_prompt:
                full_messages.append({
                    "role": "system",
                    "content": final_system_prompt
                })
            
            # 2. 添加历史对话（如果启用）
            if use_history:
                full_messages.extend(self._conversation_history.copy())
            
            # 调用基类的 chat_with_image，传入完整的消息列表
            response = self.client.chat_with_image(
                image_path=image_path,
                text_prompt=text_prompt,
                system_prompt=None,  # 已经在 messages 中包含
                max_tokens=max_tokens,
                temperature=temperature,
                image_detail=image_detail,
                messages=full_messages if full_messages else None,
                **kwargs
            )
            
            # 如果对话成功，更新内部历史记录并保存到文件
            if response.get("success") and use_history:
                # 添加用户消息到历史（图片消息用文本提示词表示）
                user_message = {
                    "role": "user",
                    "content": text_prompt if text_prompt else "[图片消息]"
                }
                self._conversation_history.append(user_message)
                
                # 添加AI回复到历史
                ai_content = response.get("content", "")
                if ai_content:
                    self._conversation_history.append({
                        "role": "assistant",
                        "content": ai_content
                    })
                
                # 保存到文件
                if self.history_file:
                    self._save_history()
        else:
            raise ValueError(f"暂不支持的服务商: {self.provider_name}")
        
        return response
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取对话历史（返回原始json，不包含系统提示词）
        
        Args:
            limit: 可选参数，指定返回的历史记录数量。如果提供，则返回最后 N 条记录（从最新的开始倒数）
        
        Returns:
            历史对话列表，不包含系统提示词。如果提供了 limit，则返回最后 N 条记录
        """
        history = self._conversation_history.copy()
        
        if limit is not None and limit > 0:
            # 返回最后 N 条记录
            return history[-limit:] if len(history) > limit else history
        
        return history
    
    def get_history_count(self) -> int:
        """
        获取历史消息的条目数量（不含系统提示词）
        
        Returns:
            历史消息的条目数量
        """
        return len(self._conversation_history)
    
    def clear_history(self):
        """清空对话历史"""
        self._conversation_history = []
        if self.log_file:
            self.log_interaction("system", "[历史已清空]")
        # 清空历史对话文件
        if self.history_file:
            self._save_history()
    
    def get_history_file(self) -> Optional[str]:
        """
        获取对话文件名
        
        Returns:
            历史对话文件路径，如果未设置则返回 None
        """
        return self.history_file
    
    def set_history(self, history: List[Dict[str, str]]):
        """
        设置历史对话（直接设置原始json，全部覆盖掉原来的历史对话，同样更新到会话文件内）
        
        Args:
            history: 历史对话列表（原始json格式，不包含系统提示词）
        """
        # 过滤掉系统提示词（确保不包含）
        filtered_history = [
            msg for msg in history 
            if msg.get('role') != 'system'
        ]
        
        # 设置到内部历史记录中
        self._conversation_history = filtered_history
        
        # 保存到文件
        if self.history_file:
            try:
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(filtered_history, f, ensure_ascii=False, indent=2)
                name = self.name or "SimpleAIClient"
                print(f"✓ [{name}] 已更新历史对话: {len(filtered_history)} 条消息")
            except Exception as e:
                name = self.name or "SimpleAIClient"
                print(f"⚠ [{name}] 保存历史对话失败: {e}")
    
    
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

