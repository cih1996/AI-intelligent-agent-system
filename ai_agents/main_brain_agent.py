#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主脑 AI Agent
负责理解用户意图并生成任务执行计划
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class MainBrainAgent(BaseAgent):
    """
    主脑 AI Agent
    负责：
    - 理解用户意图
    - 生成 ActionSpec JSON 格式的任务计划
    - 管理对话流程
    """
    
    def __init__(self, provider: str = 'deepseek', user_memory: str = "", **kwargs):
        """
        初始化主脑 AI Agent
        
        Args:
            provider: AI 服务商名称
            user_memory: 用户记忆内容（用于替换提示词中的占位符）
            **kwargs: 其他参数
        """
        super().__init__(
            name="主脑AI",
            prompt_file='prompts/example.txt',
            provider=provider,
            **kwargs
        )
        
        # 如果提示词中包含用户记忆占位符，替换它
        if user_memory and '{USER_MEMORY}' in self.system_prompt:
            self.system_prompt = self.system_prompt.replace('{USER_MEMORY}', user_memory)
            self.client.set_system_prompt(self.system_prompt, inject_mcp_tools=False)
        elif '{USER_MEMORY}' in self.system_prompt:
            self.system_prompt = self.system_prompt.replace('{USER_MEMORY}', '（暂无用户记忆）')
            self.client.set_system_prompt(self.system_prompt, inject_mcp_tools=False)
    
    def update_user_memory(self, user_memory: str):
        """
        更新用户记忆并刷新系统提示词
        
        Args:
            user_memory: 用户记忆内容
        """
        if '{USER_MEMORY}' in self.system_prompt:
            if user_memory:
                new_prompt = self.system_prompt.replace('{USER_MEMORY}', user_memory)
            else:
                new_prompt = self.system_prompt.replace('{USER_MEMORY}', '（暂无用户记忆）')
            self.update_system_prompt(new_prompt)

