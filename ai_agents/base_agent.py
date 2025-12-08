#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基础 Agent 类
所有 AI Agent 的基类，提供通用的功能
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from ai_client import SimpleAIClient


class BaseAgent:
    """
    基础 Agent 类
    提供所有 AI Agent 的通用功能：
    - 独立的 SimpleAIClient 实例
    - 独立的日志文件
    - 独立的对话历史管理
    """
    
    def __init__(
        self,
        name: str,
        prompt_file: str,
        provider: str = 'deepseek',
        log_dir: str = 'logs',
        **kwargs
    ):
        """
        初始化基础 Agent
        
        Args:
            name: Agent 名称（用于日志文件命名）
            prompt_file: 提示词文件路径
            provider: AI 服务商名称
            log_dir: 日志目录
            **kwargs: 传递给 SimpleAIClient 的额外参数
        """
        self.name = name
        self.provider = provider
        self.log_dir = log_dir
        
        # 初始化日志文件
        self.log_file = self._init_log_file()
        
        # 初始化 AI 客户端（独立实例）
        self.client = SimpleAIClient(provider=provider, **kwargs)
        
        # 加载并设置系统提示词
        self.prompt_file = prompt_file
        self.system_prompt = self._load_system_prompt()
        self.client.set_system_prompt(self.system_prompt, inject_mcp_tools=False)
        
        # 记录初始化日志
        self.log_interaction("system", self.system_prompt, is_system=True)
    
    def _init_log_file(self) -> str:
        """
        初始化日志文件
        
        Returns:
            日志文件路径
        """
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
            f.write(f"服务商: {self.provider}\n")
            f.write(f"{'='*80}\n\n")
        
        print(f"📝 [{self.name}] 日志文件: {log_path}")
        return log_path
    
    def _load_system_prompt(self) -> str:
        """
        从文件加载系统提示词
        
        Returns:
            提示词内容
        """
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
            print(f"⚠ [{self.name}] 加载提示词失败: {e}")
            return ""
    
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
    
    def chat(
        self,
        content: str,
        max_tokens: int = 1500,
        temperature: float = 0.7,
        use_history: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送消息并获取回复
        
        Args:
            content: 用户消息内容
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            use_history: 是否使用历史对话
            **kwargs: 其他参数
            
        Returns:
            响应字典
        """
        # 记录用户输入
        self.log_interaction("user", content)
        
        # 调用 AI 客户端
        response = self.client.chat(
            content=content,
            max_tokens=max_tokens,
            temperature=temperature,
            use_history=use_history,
            **kwargs
        )
        
        # 记录 AI 回复
        if response.get("success"):
            ai_content = response.get("content", "")
            self.log_interaction("assistant", ai_content)
        else:
            error_msg = response.get('message', '未知错误')
            self.log_interaction("assistant", f"[错误] {error_msg}")
        
        return response
    
    def chat_with_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1500,
        temperature: float = 0.7,
        use_history: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用消息列表发送请求（不使用历史）
        
        Args:
            messages: 消息列表
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            use_history: 是否使用历史对话
            **kwargs: 其他参数
            
        Returns:
            响应字典
        """
        # 记录所有消息
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role != 'system':  # 系统提示词已在初始化时记录
                self.log_interaction(role, content)
        
        # 调用 AI 客户端
        response = self.client.chat(
            content=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            use_history=use_history,
            **kwargs
        )
        
        # 记录 AI 回复
        if response.get("success"):
            ai_content = response.get("content", "")
            self.log_interaction("assistant", ai_content)
        else:
            error_msg = response.get('message', '未知错误')
            self.log_interaction("assistant", f"[错误] {error_msg}")
        
        return response
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.client.get_history()
    
    def clear_history(self):
        """清空对话历史"""
        self.client.clear_history()
        self.log_interaction("system", "[历史已清空]")
    
    def update_system_prompt(self, new_prompt: str, log_update: bool = False):
        """
        更新系统提示词
        
        Args:
            new_prompt: 新的提示词内容
            log_update: 是否记录到日志（默认 False，避免重复写入大量系统提示词）
        """
        self.system_prompt = new_prompt
        self.client.set_system_prompt(new_prompt, inject_mcp_tools=False)
        # 只有在明确要求时才记录到日志，避免重复写入大量系统提示词
        if log_update:
            self.log_interaction("system", "[系统提示词已更新]", is_system=True)

