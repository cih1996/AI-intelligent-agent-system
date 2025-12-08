#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆管理 AI Agent
负责管理和更新用户记忆
"""

from datetime import datetime
from typing import Dict, Any
from .base_agent import BaseAgent


class MemoryManagerAgent(BaseAgent):
    """
    记忆管理 AI Agent
    负责：
    - 根据用户输入和AI输出更新用户记忆
    - 维护用户记忆库的完整性和相关性
    """
    
    def __init__(self, provider: str = 'deepseek', **kwargs):
        """
        初始化记忆管理 AI Agent
        
        Args:
            provider: AI 服务商名称
            **kwargs: 其他参数
        """
        super().__init__(
            name="记忆管理AI",
            prompt_file='prompts/mcp_memory_manager.txt',
            provider=provider,
            **kwargs
        )
    
    def update_memory(
        self,
        user_input: str,
        ai_output: str,
        existing_memory: str = ""
    ) -> str:
        """
        更新用户记忆
        
        Args:
            user_input: 用户输入内容
            ai_output: AI输出内容
            existing_memory: 现有记忆内容（可选）
            
        Returns:
            更新后的记忆文本
        """
        # 获取当前时间（ISO格式）
        current_time_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        # 构建记忆管理输入
        memory_input = f"""用户输入：
{user_input}

AI输出：
{ai_output}

当前时间：{current_time_iso}

现有记忆库：
{existing_memory if existing_memory else '（无现有记忆）'}

请根据上述信息，更新用户记忆库。"""
        
        # 调用记忆管理 AI
        response = self.chat(
            content=memory_input,
            max_tokens=3000,
            temperature=0.3,
            use_history=False
        )
        
        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            print(f"⚠ 记忆管理AI调用失败: {error_msg}")
            # 如果失败，返回现有记忆
            return existing_memory
        
        updated_memory = response.get("content", "").strip()
        
        if not updated_memory:
            print("⚠ 记忆管理AI返回空内容，保留现有记忆")
            return existing_memory
        
        return updated_memory

