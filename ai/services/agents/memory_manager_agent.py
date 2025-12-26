#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆大纲选择 AI Agent
负责根据用户描述和当前层级，从记忆大纲中选择最相关的大纲名称
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from services.simple_client import SimpleAIClient


class MemoryManagerAgent:
    """
    记忆大纲选择 AI Agent
    负责：
    - 扫描记忆大纲目录，获取所有记忆类别（JSON文件名）
    - 根据用户描述和当前层级，选择相关的大纲名称
    - 输出大纲名称数组
    """
    
    def __init__(self, provider: str = 'deepseek', history_file: str = "default", **kwargs):
        """
        初始化记忆大纲选择 AI Agent
        
        Args:
            provider: AI 服务商名称
            history_file: 历史对话文件路径（用于区分不同用户的记忆目录）
            **kwargs: 其他参数
        """
        self.history_file = history_file
        
        # 根据 history_file 生成记忆目录路径
        # 目录：.memory/[history_file]/
        # 文件：.memory/[history_file]/*.json（每个JSON文件代表一个记忆类别）
        self.memory_base_dir = ".memory"
        self.memory_dir = os.path.join(self.memory_base_dir, history_file)
        
        self.client = SimpleAIClient(
            name="记忆大纲选择AI",
            prompt_file='prompts/mcp_memory_manager.txt',
            provider=provider,
            history_file=history_file,
            **kwargs
        )
    
    def scan_memory_outlines(self) -> Dict[str, Any]:
        """
        扫描记忆大纲目录，获取所有记忆类别的大纲结构
        
        Returns:
            记忆大纲字典，格式：{category_name: []}，只包含大纲结构，不包含具体记忆内容
        """
        outlines = {}
        
        try:
            if not os.path.exists(self.memory_dir):
                return outlines
            
            # 扫描目录下的所有 JSON 文件
            for filename in os.listdir(self.memory_dir):
                if not filename.endswith('.json'):
                    continue
                
                # 提取类别名称（去掉 .json 后缀）
                category = filename[:-5]  # 去掉 .json
                
                # 读取文件以获取记忆数量（但不读取具体内容）
                file_path = os.path.join(self.memory_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if not content:
                            outlines[category] = []
                            continue
                        
                        # 解析 JSON 以获取数组长度
                        data = json.loads(content)
                        if isinstance(data, list):
                            # 只记录数组长度，不包含具体内容
                            outlines[category] = [None] * len(data)
                        elif isinstance(data, dict):
                            # 如果是字典，转换为数组长度
                            outlines[category] = [None] * len(data)
                        else:
                            outlines[category] = []
                except (json.JSONDecodeError, Exception) as e:
                    # 如果文件格式错误，跳过
                    print(f"⚠ 读取记忆大纲文件失败 {filename}: {e}")
                    outlines[category] = []
            
            return outlines
        except Exception as e:
            print(f"⚠ 扫描记忆大纲失败: {e}")
            return {}
    
    def select_outlines(
        self,
        user_description: str,
        current_level: str = "主脑AI"
    ) -> List[str]:
        """
        根据用户描述和当前层级，选择相关的大纲名称
        
        Args:
            user_description: 用户描述或任务描述
            current_level: 当前执行的AI层级（如：主脑AI、监督AI、执行AI、MCP路由AI等）
            
        Returns:
            大纲名称数组，如：["desktop_sop", "user_preferences"]
        """
        # 扫描记忆大纲
        outlines = self.scan_memory_outlines()
        
        if not outlines:
            print("📋 [记忆大纲选择] 未找到任何记忆大纲")
            return []
        
        # 构建记忆大纲结构（只包含键名，不包含具体内容）
        outlines_json = json.dumps(outlines, ensure_ascii=False, indent=2)
        
        # 构建输入
        memory_input = (
            "用户描述：\n"
            f"{user_description}\n\n"
            "当前层级：\n"
            f"{current_level}\n\n"
            "记忆大纲（仅大纲结构）：\n"
            f"{outlines_json}\n\n"
            "请根据用户描述和当前层级，从记忆大纲中选择最相关的大纲名称，只输出 JSON 格式的大纲名称数组。"
        )
        
        self.client.clear_history()
        
        # 调用记忆大纲选择 AI
        response = self.client.chat(
            content=memory_input,
            max_tokens=1000,
            temperature=0.3,
        )
        
        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            print(f"⚠ 记忆大纲选择AI调用失败: {error_msg}")
            return []
        
        ai_response = response.get("content", "").strip()
        
        if not ai_response:
            print("⚠ 记忆大纲选择AI返回空内容")
            return []
        
        # 解析 JSON 格式的大纲名称数组
        selected_outlines = self._parse_json_from_response(ai_response)
        
        if not selected_outlines:
            print("⚠ 无法解析记忆大纲选择AI返回的JSON格式")
            return []
        
        if not isinstance(selected_outlines, list):
            print("⚠ 记忆大纲选择AI返回的不是数组格式")
            return []
        
        # 验证大纲名称是否存在于实际的大纲中
        valid_outlines = []
        for outline in selected_outlines:
            if isinstance(outline, str) and outline in outlines:
                valid_outlines.append(outline)
            else:
                print(f"⚠ 大纲名称不存在或格式错误: {outline}")
        
        if valid_outlines:
            print(f"📋 [记忆大纲选择] 选择了 {len(valid_outlines)} 个大纲: {valid_outlines}")
        else:
            print("📋 [记忆大纲选择] 未选择任何相关大纲")
        
        return valid_outlines
    
    def _parse_json_from_response(self, response_text: str) -> Optional[List[str]]:
        """
        从AI响应中解析JSON数组（大纲名称数组）
        
        Args:
            response_text: AI响应文本
            
        Returns:
            解析后的JSON数组，如果解析失败返回None
        """
        # 尝试直接解析 JSON
        try:
            data = json.loads(response_text.strip())
            if isinstance(data, list):
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
                    if isinstance(data, list):
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
                        if isinstance(data, list):
                            return data
                    except:
                        pass
                    start_idx = -1
        
        return None
    
    def get_memory_file_path(self, category: str) -> str:
        """
        获取指定类别的记忆文件路径
        
        Args:
            category: 记忆类别名称（如：desktop_sop）
            
        Returns:
            记忆文件路径
        """
        return os.path.join(self.memory_dir, f"{category}.json")
