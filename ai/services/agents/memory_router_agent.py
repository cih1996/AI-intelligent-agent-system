#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆路由选择 AI Agent
负责从选定大纲的全部记忆（shared）中，根据当前执行阶段选择合适的记忆payload路径
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from services.simple_client import SimpleAIClient


class MemoryRouterAgent:
    """
    记忆路由选择 AI Agent
    负责：
    - 从选定大纲的JSON文件中读取全部记忆（shared格式）
    - 根据当前执行阶段选择合适的payload路径
    - 输出payload的JSON路径数组
    """
    
    def __init__(self, provider: str = 'deepseek', history_file: str = "default", **kwargs):
        """
        初始化记忆路由选择 AI Agent
        
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
            name="记忆路由选择AI",
            prompt_file='prompts/mcp_memory_router.txt',
            provider=provider,
            history_file=history_file,
            **kwargs
        )
    
    def load_category_memories(self, category: str) -> List[Dict[str, Any]]:
        """
        加载指定类别的全部记忆
        
        Args:
            category: 记忆类别名称（如：desktop_sop）
            
        Returns:
            记忆列表，格式：[{key: "mem_001", shared: {...}, ...}, ...]
        """
        memory_file = os.path.join(self.memory_dir, f"{category}.json")
        
        try:
            if not os.path.exists(memory_file):
                return []
            
            with open(memory_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                
                # 解析 JSON
                data = json.loads(content)
                
                if isinstance(data, list):
                    # 如果是数组，直接返回
                    return data
                elif isinstance(data, dict):
                    # 如果是字典，转换为数组
                    return list(data.values())
                else:
                    return []
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠ 加载记忆文件失败 {category}: {e}")
            return []
    
    def select_payload_paths(
        self,
        categories: List[str],
        user_input: str,
        current_stage: str = "主脑AI"
    ) -> List[Dict[str, Any]]:
        """
        从选定大纲的全部记忆中，根据当前执行阶段选择合适的payload路径，并返回完整的记忆数据
        
        Args:
            categories: 选定的记忆类别列表（如：["desktop_sop", "user_preferences"]）
            user_input: 用户输入或任务描述
            current_stage: 当前执行阶段（如：监督AI、主脑AI、执行AI、MCP路由AI等）
            
        Returns:
            完整的记忆数据列表，格式：[{"path": "desktop_sop.mem_001", "payload": "记忆文本内容"}, ...]
        """
        # 按大纲格式加载所有选定类别的记忆
        memories_by_category = {}
        all_memories_map = {}  # 用于验证路径：{category.key: memory}
        
        for category in categories:
            memories = self.load_category_memories(category)
            if not memories:
                continue
            
            # 将记忆转换为字典格式，key为记忆的key字段
            category_memories = {}
            for memory in memories:
                if isinstance(memory, dict) and 'key' in memory:
                    key = memory.get('key')
                    category_memories[key] = memory
                    # 同时保存到全局映射中，用于验证路径
                    all_memories_map[f"{category}.{key}"] = memory
            
            if category_memories:
                memories_by_category[category] = category_memories
        
        if not memories_by_category:
            print(f"📋 [记忆路由] 类别 {categories} 中未找到任何记忆")
            return []
        
        # 构建记忆结构JSON（按大纲格式组织，用于展示给AI）
        memories_json = json.dumps(memories_by_category, ensure_ascii=False, indent=2)
        
        # 构建输入（替换提示词中的 {STAGE} 占位符）
        memory_input = "请根据当前执行阶段和提供的记忆结构，选择合适的payload路径，只输出 JSON 格式的路径数组。"
        
        self.client.clear_history()
        self.client.update_system_prompt({'{TASK_DESCRIPTION}': user_input,'{STAGE}': current_stage, '{MEMORY_DATA}': memories_json})
        # 调用记忆路由选择 AI
        response = self.client.chat(
            content=memory_input,
            max_tokens=2000,
            temperature=0.3,
        )
        
        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            print(f"⚠ 记忆路由选择AI调用失败: {error_msg}")
            return []
        
        ai_response = response.get("content", "").strip()
        
        if not ai_response:
            #print("⚠ 记忆路由选择AI返回空内容")
            return []
        
        # 解析 JSON 格式的路径数组
        payload_paths = self._parse_json_from_response(ai_response)
        
        if not payload_paths:
            #print("⚠ 无法解析记忆路由选择AI返回的JSON格式")
            return []
        
        if not isinstance(payload_paths, list):
            #print("⚠ 记忆路由选择AI返回的不是数组格式")
            return []
        
        # 验证路径是否有效，并获取payload数据
        memory_data = []
        for path in payload_paths:
            if isinstance(path, str) and self._validate_path(path, memories_by_category):
                payload = self.get_payload_by_path(path)
                if payload:
                    memory_data.append({
                        "path": path,
                        "payload": payload
                    })
                else:
                    print(f"⚠ 无法获取路径的payload数据: {path}")
            else:
                print(f"⚠ 路径无效或不存在: {path}")
        
        if memory_data:
            print(f"📋 [记忆路由] 选择了 {len(memory_data)} 个payload路径，已获取完整记忆数据")
        else:
            print("📋 [记忆路由] 未选择任何相关路径")
        
        return memory_data
    
    def _validate_path(self, path: str, memories_by_category: Dict[str, Dict[str, Dict[str, Any]]]) -> bool:
        """
        验证路径是否有效
        
        Args:
            path: JSON路径，格式：category.key
            memories_by_category: 按大纲格式组织的记忆字典，格式：{category: {key: memory, ...}, ...}
            
        Returns:
            路径是否有效
        """
        try:
            # 解析路径，只支持2段路径：category.key
            parts = path.split('.')
            if len(parts) != 2:  # 必须正好是2段：category.key
                return False
            
            # 第一部分应该是category
            category = parts[0]
            if category not in memories_by_category:
                return False
            
            # 第二部分应该是记忆的key
            key = parts[1]
            if key not in memories_by_category[category]:
                return False
            
            # 路径有效
            return True
        except Exception:
            return False
    
    def _parse_json_from_response(self, response_text: str) -> Optional[List[str]]:
        """
        从AI响应中解析JSON数组（路径数组）
        
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
    
    def get_payload_by_path(self, path: str) -> Optional[Any]:
        """
        根据路径获取payload数据
        
        Args:
            path: JSON路径，格式：category.key，如：desktop_sop.mem_001
            
        Returns:
            payload数据（字符串），如果路径无效返回None
        """
        try:
            # 解析路径，只支持2段路径：category.key
            parts = path.split('.')
            if len(parts) != 2:  # 必须正好是2段：category.key
                return None
            
            # 第一部分是category
            category = parts[0]
            # 第二部分是key
            key = parts[1]
            
            # 加载对应类别的记忆
            memories = self.load_category_memories(category)
            memory = None
            for mem in memories:
                if isinstance(mem, dict) and mem.get('key') == key:
                    memory = mem
                    break
            
            if not memory:
                return None
            
            # 直接返回payload字段的值
            return memory.get('payload')
        except Exception:
            return None

    def payload_to_markdown(self, payload: Any, indent: int = 0) -> str:
        """
        将payload(json/dict/list/str) 格式化为 MarkDown 文本返回
        如果传入的是完整的记忆数据列表（包含path和payload），则一次性格式化所有记忆

        Args:
            payload: 
                - 完整的记忆数据列表，格式：[{"path": "...", "payload": {...}}, ...]
                - 或任意json类型（dict/list/str/int/float/bool/None）
            indent: 当前缩进层级，递归内部使用

        Returns:
            Markdown格式化的字符串
        """
        # 检查是否是完整的记忆数据列表（select_payload_paths返回的格式）
        if isinstance(payload, list) and len(payload) > 0:
            first_item = payload[0]
            if isinstance(first_item, dict) and "path" in first_item and "payload" in first_item:
                # 这是完整的记忆数据列表，一次性格式化所有记忆
                lines = []
                for idx, memory_item in enumerate(payload, 1):
                    path = memory_item.get("path", "")
                    item_payload = memory_item.get("payload")
                    
                    # 添加路径标题
                    lines.append(f"## 记忆 [{idx}]: {path}\n")
                    # 格式化payload
                    formatted = self._format_single_payload(item_payload, indent=0)
                    lines.append(formatted)
                    lines.append("")  # 空行分隔
                
                return "\n".join(lines)
        
        # 否则按原来的逻辑处理单个payload
        return self._format_single_payload(payload, indent)
    
    def _format_single_payload(self, payload: Any, indent: int = 0) -> str:
        """
        格式化单个payload为Markdown（内部方法）
        
        Args:
            payload: 任意json类型（dict/list/str/int/float/bool/None）
            indent: 当前缩进层级，递归内部使用
            
        Returns:
            Markdown格式化的字符串
        """
        def _md_keyval(key, val, level):
            if isinstance(val, (dict, list)):
                return f"{'  ' * level}- **{key}**:\n{self._format_single_payload(val, indent=level+1)}"
            else:
                if val is None:
                    sval = '`null`'
                elif isinstance(val, bool):
                    sval = "`true`" if val else "`false`"
                elif isinstance(val, (int, float)):
                    sval = f"`{val}`"
                elif isinstance(val, str):
                    sval = val.replace('\n', ' ')
                    sval = f"`{sval}`" if len(sval) < 60 and sval.find('`') < 0 else f"\n{'  ' * (level+1)}```\n{sval}\n{'  ' * (level+1)}```\n"
                else:
                    sval = str(val)
                return f"{'  ' * level}- **{key}**: {sval}"
        
        prefix = '  ' * indent
        if isinstance(payload, dict):
            lines = []
            for k, v in payload.items():
                lines.append(_md_keyval(k, v, indent))
            return '\n'.join(lines)
        elif isinstance(payload, list):
            lines = []
            for idx, item in enumerate(payload):
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}- [{idx+1}]:\n{self._format_single_payload(item, indent=indent+1)}")
                else:
                    lines.append(f"{prefix}- `{item}`")
            return '\n'.join(lines)
        elif isinstance(payload, str):
            sval = payload.replace('\n', ' ')
            return f"{prefix}`{sval}`"
        elif payload is None:
            return f"{prefix}`null`"
        elif isinstance(payload, bool):
            return f"{prefix}`{'true' if payload else 'false'}`"
        elif isinstance(payload, (int, float)):
            return f"{prefix}`{payload}`"
        else:
            return f"{prefix}`{str(payload)}`"