#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主脑 AI Agent
负责理解用户意图并生成任务执行计划
"""

from typing import Dict, Any, Optional
import json
import re
from werkzeug.wrappers import response
from services.simple_client import SimpleAIClient


class MainBrainAgent:
    """
    主脑 AI Agent
    负责：
    - 理解用户意图
    - 生成 ActionSpec JSON 格式的任务计划
    - 管理对话流程
    """
    
    def __init__(self, provider: str = 'deepseek', history_file: str = "default", **kwargs):
        """
        初始化主脑 AI Agent
        
        Args:
            provider: AI 服务商名称
            history_file: 历史对话文件路径
            **kwargs: 其他参数
        """
        self.client = SimpleAIClient(
            name="主脑AI",
            prompt_file='prompts/mcp_main_brain.txt',
            provider=provider,
            history_file=history_file,
            **kwargs
        )

     
    
    def update_user_memory(self, user_memory: str, mcp_tools: str):
        """
        更新用户记忆并刷新系统提示词
        
        Args:
            user_memory: 用户记忆内容
            mcp_tools: MCP工具列表
        """
        self.client.update_system_prompt({'{USER_MEMORY}': user_memory,'{MCP_TOOLS}': mcp_tools})
    
    
    def chat(self, *args, **kwargs):
        """调用客户端的 chat 方法"""    
        response = self.client.chat(*args, **kwargs)
        if(response['success']):
            return self.parse_main_brain_json(response['content'])
        raise Exception(response['message'])

    
    def get_history(self, limit: Optional[int] = None):
        """获取对话历史"""
        return self.client.get_history(limit)
    
    def get_history_count(self):
        """获取对话历史条目数量"""
        return self.client.get_history_count()

    def clear_history(self):
        """清空对话历史"""
        return self.client.clear_history()

    
    def parse_main_brain_json(self,response_text: str) -> Optional[Dict[str, Any]]:
        """
        解析主脑输出的 ActionSpec JSON 格式
        
        Returns:
            解析后的 JSON 字典，如果解析失败返回 None
        """
        # 尝试直接解析 JSON
        try:
            data = json.loads(response_text.strip())
            if "actions" in data:
                return data
        except:
            pass
        
        # 尝试从代码块中提取
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(code_block_pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match.strip())
                if "actions" in data:
                    return data
            except:
                continue
        
        # 尝试查找 JSON 对象（使用括号匹配）
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(response_text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = response_text[start_idx:i+1]
                    try:
                        data = json.loads(json_str)
                        if "actions" in data:
                            return data
                    except:
                        pass
                    start_idx = -1
        
        return None
