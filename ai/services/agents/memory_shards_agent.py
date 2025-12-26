#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆碎片增删改检测 AI Agent
负责从用户输入和AI输出中提取、分类、更新和管理用户记忆库
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from services.simple_client import SimpleAIClient


class MemoryShardsAgent:
    """
    记忆碎片增删改检测 AI Agent
    负责：
    - 从用户输入和AI输出中检测记忆变更
    - 输出记忆变更操作（新增/更新/删除）
    - 返回JSON格式的变更操作数组
    """
    
    def __init__(self, provider: str = 'deepseek', history_file: str = "default", **kwargs):
        """
        初始化记忆碎片增删改检测 AI Agent
        
        Args:
            provider: AI 服务商名称
            history_file: 历史对话文件路径（用于区分不同用户的记忆目录）
            **kwargs: 其他参数
        """
        self.history_file = history_file
        
        # 根据 history_file 生成记忆目录路径
        # 目录：.memory/[history_file]/
        # 文件：.memory/[history_file]/{category}.json
        self.memory_base_dir = ".memory"
        self.memory_dir = os.path.join(self.memory_base_dir, history_file)
        
        self.client = SimpleAIClient(
            name="记忆碎片增删改检测AI",
            prompt_file='prompts/mcp_memory_shards.txt',
            provider=provider,
            history_file=history_file,
            **kwargs
        )
    
    def detect_memory_changes(
        self,
        existing_memories: str,
        raw_dialogue_json: str
    ) -> List[Dict[str, Any]]:
        """
        检测记忆变更，返回变更操作数组

        Args:
            existing_memories: 现有的记忆数据，字符串类型
            raw_dialogue_json: 完整的原始AI对话JSON文本，字符串类型

        Returns:
            变更操作数组，格式：[{key, action, category, ...}, ...]
            如果没有变更，返回空数组 []
        """
        # 构建输入，直接传递原始AI对话JSON文本给模型处理
        memory_input = (
            "以下是现有的记忆数据，请分析并检测记忆变更，输出 JSON 格式的变更操作数组：\n\n"
            f"{existing_memories}\n\n"
            "以下是完整的AI对话JSON文本，请分析并检测记忆变更，输出 JSON 格式的变更操作数组：\n\n"
            f"{raw_dialogue_json}\n\n"
            "只需要输出变更操作的 JSON 数组即可，无需其它说明。"
        )

        self.client.clear_history()

        # 调用记忆碎片增删改检测 AI
        response = self.client.chat(
            content=memory_input,
            max_tokens=3000,
            temperature=0.3,
        )

        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            print(f"⚠ 记忆碎片增删改检测AI调用失败: {error_msg}")
            return []

        print(response)
        ai_response = response.get("content", "").strip()
       
        if not ai_response:
            #print("⚠ 记忆碎片增删改检测AI返回空内容")
            return []

        # 解析 JSON 格式的变更操作数组
        changes = self._parse_json_from_response(ai_response)

        if not changes:
            #print("⚠ 无法解析记忆碎片增删改检测AI返回的JSON格式,可能不需要变更")
            return []

        if not isinstance(changes, list):
            #print("⚠ 记忆碎片增删改检测AI返回的不是数组格式")
            return []

        # 验证变更操作的格式
        valid_changes = []
        for change in changes:
            if not isinstance(change, dict):
                continue

            # 验证必需字段
            if 'action' not in change:
                print(f"⚠ 变更操作缺少 action 字段: {change}")
                continue

            action = change.get('action')

            if action == 'add':
                # 验证新增/更新操作的必需字段
                required_fields = ['key', 'category','importance', 'source']
                missing_fields = [field for field in required_fields if field not in change]
                if missing_fields:
                    print(f"⚠ 新增/更新操作缺少必需字段 {missing_fields}: {change}")
                    continue

               
                valid_changes.append(change)

            elif action == 'del':
                # 验证删除操作的必需字段
                required_fields = ['key', 'category']
                missing_fields = [field for field in required_fields if field not in change]
                if missing_fields:
                    print(f"⚠ 删除操作缺少必需字段 {missing_fields}: {change}")
                    continue

                valid_changes.append(change)

            else:
                print(f"⚠ 未知的操作类型: {action}")
                continue
        return valid_changes

    def _parse_json_from_response(self, response_text: str) -> Optional[List[Dict[str, Any]]]:
        """
        从AI响应中解析JSON数组（变更操作数组）
        
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
    
    def apply_memory_changes(self, changes: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        应用变更操作到记忆文件
        
        Args:
            changes: 变更操作数组
            
        Returns:
            应用结果统计，格式：{"added": 数量, "updated": 数量, "deleted": 数量}
        """
        if not changes:
            return {"added": 0, "updated": 0, "deleted": 0}
        
        stats = {"added": 0, "updated": 0, "deleted": 0}
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        # 按类别分组变更操作
        changes_by_category = {}
        for change in changes:
            category = change.get('category')
            if not category:
                continue
            if category not in changes_by_category:
                changes_by_category[category] = []
            changes_by_category[category].append(change)
        
        # 逐个类别处理
        for category, category_changes in changes_by_category.items():
            memory_file = os.path.join(self.memory_dir, f"{category}.json")
            
            # 加载现有记忆
            memories = self._load_category_memories(category)
            memories_dict = {mem.get('key'): mem for mem in memories if 'key' in mem}
            
            # 应用变更
            for change in category_changes:
                action = change.get('action')
                key = change.get('key')
                
                if action == 'add':
                    # 新增或更新记忆
                    if key in memories_dict:
                        # 更新现有记忆
                        old_memory = memories_dict[key]
                        old_trigger_count = old_memory.get('trigger_count', 0)
                        
                        # 构建新记忆（保留原有字段，更新新字段）
                        new_memory = change.copy()
                        new_memory['trigger_count'] = old_trigger_count + 1
                        new_memory['updated_at'] = current_time
                        new_memory['last_triggered'] = current_time
                        # 保留原有的 created_at
                        if 'created_at' in old_memory:
                            new_memory['created_at'] = old_memory['created_at']
                        else:
                            new_memory['created_at'] = current_time
                        
                        # 移除 action 字段（不是记忆字段）
                        new_memory.pop('action', None)
                        
                        memories_dict[key] = new_memory
                        stats["updated"] += 1
                        print(f"  ✓ 更新记忆: {key} ({category}) , 记忆内容: {new_memory.get('payload')}")
                    else:
                        # 新增记忆
                        new_memory = change.copy()
                        new_memory['trigger_count'] = 1
                        new_memory['created_at'] = current_time
                        new_memory['updated_at'] = current_time
                        new_memory['last_triggered'] = current_time
                        
                        # 移除 action 字段
                        new_memory.pop('action', None)
                        
                        memories_dict[key] = new_memory
                        stats["added"] += 1
                        print(f"  ✓ 新增记忆: {key} ({category}) , 记忆内容: {new_memory.get('payload')}")
                
                elif action == 'del':
                    # 删除记忆
                    if key in memories_dict:
                        del memories_dict[key]
                        stats["deleted"] += 1
                        print(f"  ✓ 删除记忆: {key} ({category})")
                    else:
                        print(f"  ⚠ 记忆不存在，无法删除: {key} ({category})")
            
            # 保存回文件
            self._save_category_memories(category, list(memories_dict.values()))
        
        return stats
    
    def _load_category_memories(self, category: str) -> List[Dict[str, Any]]:
        """
        加载指定类别的记忆
        
        Args:
            category: 记忆类别名称
            
        Returns:
            记忆列表
        """
        memory_file = os.path.join(self.memory_dir, f"{category}.json")
        
        try:
            if not os.path.exists(memory_file):
                return []
            
            with open(memory_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return list(data.values())
                else:
                    return []
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠ 加载记忆文件失败 {category}: {e}")
            return []
    
    def _save_category_memories(self, category: str, memories: List[Dict[str, Any]]):
        """
        保存指定类别的记忆到文件
        
        Args:
            category: 记忆类别名称
            memories: 记忆列表
        """
        memory_file = os.path.join(self.memory_dir, f"{category}.json")
        
        try:
            os.makedirs(self.memory_dir, exist_ok=True)
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠ 保存记忆文件失败 {category}: {e}")
    
    def format_changes_summary(self, changes: List[Dict[str, Any]]) -> str:
        """
        格式化变更操作摘要（用于日志或显示）
        
        Args:
            changes: 变更操作数组
            
        Returns:
            格式化的摘要文本
        """
        if not changes:
            return "无变更操作"
        
        summary_parts = []
        add_count = sum(1 for c in changes if c.get('action') == 'add')
        del_count = sum(1 for c in changes if c.get('action') == 'del')
        
        if add_count > 0:
            summary_parts.append(f"新增/更新: {add_count}")
        if del_count > 0:
            summary_parts.append(f"删除: {del_count}")
        
        return ", ".join(summary_parts)

