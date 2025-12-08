#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
监督 AI Agent
负责审核主脑 AI 的输出，确保安全性和正确性
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_agent import BaseAgent


class SupervisorAgent(BaseAgent):
    """
    监督 AI Agent
    负责：
    - 审核主脑 AI 的输出
    - 判断输出的合理性、安全性和正确性
    - 提供反馈和建议
    """
    
    def __init__(self, provider: str = 'deepseek', **kwargs):
        """
        初始化监督 AI Agent
        
        Args:
            provider: AI 服务商名称
            **kwargs: 其他参数
        """
        super().__init__(
            name="监督AI",
            prompt_file='prompts/mcp_supervisor.txt',
            provider=provider,
            **kwargs
        )
    
    def supervise(
        self,
        user_input: str,
        main_brain_output: str,
        main_brain_json: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        监督主脑 AI 的输出
        
        Args:
            user_input: 用户原始输入
            main_brain_output: 主脑 AI 的原始输出文本
            main_brain_json: 解析后的主脑 AI JSON
            conversation_history: 对话历史（可选）
            
        Returns:
            监督决策字典，格式: {
                'decision': 'APPROVE' | 'REJECT',
                'reason': str,
                'suggestions': List[str] (可选),
                'feedback': str (可选)
            }
        """
        # 格式化对话历史
        history_text = ""
        if conversation_history:
            filtered_history = [msg for msg in conversation_history if msg.get('role') in ['user', 'assistant']]
            if filtered_history:
                history_text = "\n对话历史：\n"
                for i, msg in enumerate(filtered_history, 1):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    history_text += f"{i}. [{role}]: {content}\n"
            else:
                history_text = "\n对话历史：无（首次对话）\n"
        else:
            history_text = "\n对话历史：无（首次对话）\n"
        
        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_weekday = datetime.now().strftime("%A")
        
        # 构建监督输入
        supervisor_input = (
            f"[当前时间: {current_time} ({current_date} {current_weekday})]\n\n"
            "用户原始请求：\n"
            f"{user_input}\n"
            f"{history_text}\n"
            "────────────────────────────────\n"
            "请结合用户原始请求、对话历史和当前时间，审核主脑 AI 的输出，判断其合理性、安全性和正确性。"
        )
        
        # 调用监督 AI
        response = self.chat_with_messages(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": supervisor_input}
            ],
            max_tokens=500,
            temperature=0.3,
            use_history=False
        )
        
        if not response.get("success"):
            # 如果监督 AI 调用失败，默认放行
            print("⚠ [监督AI] 调用失败，默认放行")
            return {
                'decision': 'APPROVE',
                'reason': '监督 AI 调用失败，默认放行'
            }
        
        supervisor_output = response.get("content", "")
        
        # 解析监督决策
        supervisor_decision = self._parse_decision(supervisor_output)
        
        if not supervisor_decision:
            # 如果解析失败，默认放行
            print("⚠ 无法解析监督决策，默认放行")
            return {
                'decision': 'APPROVE',
                'reason': '无法解析监督决策，默认放行'
            }
        
        decision = supervisor_decision.get('decision', 'APPROVE')
        
        if decision == 'APPROVE':
            print(f"✓ 监督通过: {supervisor_decision.get('reason', '')}")
        else:
            print(f"✗ 监督驳回: {supervisor_decision.get('reason', '')}")
            if supervisor_decision.get('suggestions'):
                print("建议:")
                for suggestion in supervisor_decision.get('suggestions', []):
                    print(f"  - {suggestion}")
        
        return supervisor_decision
    
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

