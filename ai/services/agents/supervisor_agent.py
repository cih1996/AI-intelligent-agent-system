#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
监督 AI Agent
负责审核主脑 AI 的输出，确保安全性和正确性
"""

import json
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from services.simple_client import SimpleAIClient


class SupervisorAgent:
    """
    监督 AI Agent
    负责：
    - 审核主脑 AI 的输出
    - 判断输出的合理性、安全性和正确性
    - 提供反馈和建议
    """
    
    def __init__(self, provider: str = 'deepseek', history_file: str = "default", chat_callback: Optional[Callable[[Dict[str, Any], str], None]] = None, stream_callback: Optional[Callable[[Dict[str, Any], str], None]] = None,**kwargs):
        """
        初始化监督 AI Agent
        
        Args:
            provider: AI 服务商名称
            history_file: 历史对话文件路径
            chat_callback: 聊天回调函数
            stream_callback: 传输回调函数
            **kwargs: 其他参数
        """
        self.client = SimpleAIClient(
            name="监督AI",
            prompt_file='prompts/mcp_supervisor.txt',
            provider=provider,
            history_file=history_file,
            chat_callback=chat_callback,
            stream_callback=stream_callback,
            **kwargs
        )
        self.system_prompt = self.client.system_prompt
    
    def supervise(
        self,
        user_input: str,
        main_brain_output: str,
        conversation_history: str = None
    ) -> Dict[str, Any]:
        """
        监督主脑 AI 的输出
        
        Args:
            user_input: 用户原始输入
            main_brain_output: 主脑 AI 的原始输出文本
            conversation_history: 对话历史（可选）
            
        Returns:
            监督决策字典，格式: {
                'decision': 'APPROVE' | 'REJECT',
                'reason': str,
                'suggestions': List[str] (可选),
                'feedback': str (可选)
            }
        """
  
        # 构建监督输入
        supervisor_input = (
            "用户原始请求：\n"
            f"{user_input}\n"
            "主脑响应结果：\n"
            f"{json.dumps(main_brain_output, indent=2, ensure_ascii=False)}\n"
            "请结合用户原始请求、主脑输出结果，审核主脑 AI 的输出，判断其合理性、安全性和正确性。"
        )
        
        # 调用监督 AI
        response = self.client.chat(
            content=supervisor_input,
            max_tokens=500,
            temperature=0.3,
        )
        
        if not response.get("success"):
            # 如果监督 AI 调用失败，默认放行
            print("⚠ [监督AI] 调用失败，默认放行")
            return {
                'decision': 'APPROVE',
                'reason': '监督 AI 调用失败，默认放行'
            }
        
        supervisor_output = response['content']
        # 解析监督决策
        supervisor_decision = self._parse_decision(supervisor_output)
        if not supervisor_decision:
            # 如果解析失败，默认放行
            return {
                'decision': 'APPROVE',
                'reason': '无法解析监督决策，默认放行'
            } 
        return supervisor_decision
    
    def clear_history(self):
        self.client.clear_history()
        
    def update_user_memory(self, supervisor_memory: str):
        """
        更新监督记忆并刷新系统提示词
        
        Args:
            supervisor_memory: 监督记忆内容
        """
        self.client.update_system_prompt({'{USER_MEMORY}': supervisor_memory})
    
    def _parse_decision(self, output: str) -> Optional[Dict[str, Any]]:
        """
        解析监督决策 JSON
        
        Args:
            output: 监督 AI 的输出文本
            
        Returns:
            解析后的决策字典，如果解析失败返回 None
        """
        # 尝试直接解析 JSON
        try:
            return json.loads(output.strip())
        except:
            pass
        
        # 尝试从代码块中提取
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(code_block_pattern, output, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        return None

