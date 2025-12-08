#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行 AI Agent
负责选择具体的工具方法并生成执行参数
"""

import json
import re
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent


class ExecutorAgent(BaseAgent):
    """
    执行 AI Agent
    负责：
    - 从推荐插件中选择具体的工具方法
    - 生成工具执行所需的参数
    - 支持单个和批量调用
    """
    
    def __init__(self, provider: str = 'deepseek', **kwargs):
        """
        初始化执行 AI Agent
        
        Args:
            provider: AI 服务商名称
            **kwargs: 其他参数
        """
        super().__init__(
            name="执行AI",
            prompt_file='prompts/mcp_tool_executor.txt',
            provider=provider,
            **kwargs
        )
    
    def execute_task(
        self,
        recommended_plugins: List[Dict[str, Any]],
        task_description: str,
        user_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行任务：选择工具方法并生成参数（支持 action 机制）
        
        Args:
            recommended_plugins: 路由AI推荐的所有插件列表
            task_description: 任务描述
            user_params: 用户提供的参数
            
        Returns:
            包含执行计划的字典，格式: {
                'success': bool,
                'action': str,     # 'call' 或 'finish'
                'calls': list,     # 工具调用列表（action='call' 时）
                'summary': str,    # 任务总结（action='finish' 时）
                'extracted_data': dict,  # 提取的数据（action='finish' 时）
                'error': str,      # 错误信息（如果失败）
                'ai_response': str  # AI 的原始响应
            }
        """
        if not recommended_plugins:
            return {
                'success': False,
                'action': None,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': '没有推荐的插件',
                'ai_response': None
            }
        
        # 格式化所有推荐插件的完整信息
        plugins_info_text = self._format_plugins_info(recommended_plugins)
        print(" ========== 格式化后的参数说明 ================")
        print(plugins_info_text)
        # 更新系统提示词（注入插件信息）
        updated_prompt = self.system_prompt.replace('{PLUGINS_INFO}', plugins_info_text)
        
        # 更新系统提示词（保持历史记录）
        self.update_system_prompt(updated_prompt)
        
        # 构建执行输入
        user_params_text = json.dumps(user_params, ensure_ascii=False, indent=2) if user_params else '无'
        executor_input = (
            f"任务描述: {task_description}\n"
            f"用户提供的参数: {user_params_text}\n"
            f"请根据上述信息，从所有推荐插件中选择合适的工具方法并生成可执行的参数。"
            f"你可以只使用一个插件的方法，也可以使用多个插件的方法。"
        )
        
        # 调用执行 AI（使用历史记录）
        response = self.chat(
            content=executor_input,
            max_tokens=2000,
            temperature=0.3,
            use_history=True  # 使用历史记录
        )
        
        executor_output = response.get("content", "")
        
        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            return {
                'success': False,
                'action': None,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': f'工具执行 AI 调用失败: {error_msg}',
                'ai_response': executor_output
            }
        
        # 解析执行 AI 的输出
        parsed_result = self._parse_executor_output(executor_output)
        
        if not parsed_result:
            return {
                'success': False,
                'action': None,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': '无法从工具执行 AI 输出中解析 JSON 格式。输出可能被截断，请检查 max_tokens 设置是否足够大。',
                'ai_response': executor_output
            }
        
        # 检查 action 字段
        action = parsed_result.get('action', 'call')  # 默认为 'call' 以保持向后兼容
        
        if action == 'finish':
            # 任务完成
            return {
                'success': True,
                'action': 'finish',
                'calls': None,
                'summary': parsed_result.get('summary', ''),
                'extracted_data': parsed_result.get('extracted_data', {}),
                'error': None,
                'ai_response': executor_output
            }
        elif action == 'call':
            # 需要执行工具调用（统一使用 calls 数组格式）
            calls = parsed_result.get('calls', [])
            if not calls or not isinstance(calls, list):
                return {
                    'success': False,
                    'action': 'call',
                    'calls': None,
                    'summary': None,
                    'extracted_data': None,
                    'error': 'action 为 "call" 但缺少 calls 字段或格式错误（即使是单个调用，也必须使用 calls 数组格式）',
                    'ai_response': executor_output
                }
            
            return {
                'success': True,
                'action': 'call',
                'calls': calls,
                'summary': None,
                'extracted_data': None,
                'error': None,
                'ai_response': executor_output
            }
        else:
            return {
                'success': False,
                'action': action,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': f'未知的 action 类型: {action}',
                'ai_response': executor_output
            }
    
    def _format_plugins_info(self, recommended_plugins: List[Dict[str, Any]]) -> str:
        """
        格式化插件信息为文本，包含完整的参数说明
        
        Args:
            recommended_plugins: 推荐的插件列表
            
        Returns:
            格式化后的插件信息文本
        """
        plugins_info_text = ""
        for plugin_idx, recommended_plugin in enumerate(recommended_plugins, 1):
            plugin_name = recommended_plugin['name']
            plugin_info = recommended_plugin['plugin_info']
            plugin_description = plugin_info.get('manifest', {}).get('description', '')
            tools = plugin_info.get('tools', [])
            
            plugins_info_text += f"\n### 插件 {plugin_idx}: {plugin_name}\n"
            plugins_info_text += f"描述: {plugin_description}\n\n"
            plugins_info_text += f"**该插件的所有方法**（请严格按照以下方法名称使用，不要使用示例中的方法名称）:\n\n"
            
            if not tools:
                plugins_info_text += "（无可用方法）\n"
            else:
                for i, tool_def in enumerate(tools, 1):
                    tool_name = tool_def.get('name', '')
                    tool_desc = tool_def.get('description', '')
                    
                    # 同时检查 input_schema 和 inputSchema（camelCase）
                    input_schema = tool_def.get('input_schema') or tool_def.get('inputSchema', {})
                    properties = input_schema.get('properties', {}) if input_schema else {}
                    required = input_schema.get('required', []) if input_schema else []
                    
                    plugins_info_text += f"{i}. **{tool_name}**\n"
                    plugins_info_text += f"   描述: {tool_desc}\n"
                    
                    if properties:
                        plugins_info_text += f"   参数列表:\n"
                        for param_name, param_info in properties.items():
                            param_type = param_info.get('type', 'unknown')
                            param_desc = param_info.get('description', '')
                            is_required = param_name in required
                            required_text = "【必填】" if is_required else "【可选】"
                            
                            # 处理枚举类型
                            if 'enum' in param_info:
                                enum_values = param_info['enum']
                                plugins_info_text += f"     - {param_name} ({param_type}) {required_text}: {param_desc}\n"
                                plugins_info_text += f"       可选值: {', '.join([str(v) for v in enum_values])}\n"
                            # 处理数组类型
                            elif param_type == 'array' and 'items' in param_info:
                                items_type = param_info['items'].get('type', 'unknown')
                                plugins_info_text += f"     - {param_name} (array<{items_type}>) {required_text}: {param_desc}\n"
                            # 处理对象类型
                            elif param_type == 'object' and 'properties' in param_info:
                                plugins_info_text += f"     - {param_name} (object) {required_text}: {param_desc}\n"
                            else:
                                plugins_info_text += f"     - {param_name} ({param_type}) {required_text}: {param_desc}\n"
                    else:
                        plugins_info_text += f"   参数: 无参数\n"
                    
                    plugins_info_text += "\n"
            
            plugins_info_text += "\n"
        
        return plugins_info_text
    
    def _parse_executor_output(self, output: str) -> Optional[Dict[str, Any]]:
        """
        解析执行 AI 的输出 JSON
        
        Args:
            output: 执行 AI 的输出文本
            
        Returns:
            解析后的 JSON 字典，如果解析失败返回 None
        """
        output_stripped = output.strip()
        
        # 方法1: 尝试直接解析
        try:
            return json.loads(output_stripped)
        except json.JSONDecodeError as e:
            if 'Unterminated string' in str(e) or 'Expecting' in str(e):
                pass
        except:
            pass
        
        # 方法2: 尝试从代码块中提取
        code_block_pattern = r'```(?:json)?'
        code_blocks = list(re.finditer(code_block_pattern, output))
        
        for block_match in code_blocks:
            start_pos = block_match.end()
            end_pos = output.find('```', start_pos)
            if end_pos == -1:
                continue
            
            code_content = output[start_pos:end_pos].strip()
            
            # 先尝试直接解析
            try:
                return json.loads(code_content)
            except:
                pass
            
            # 如果直接解析失败，使用括号匹配提取完整的JSON对象
            brace_count = 0
            json_start = -1
            for i, char in enumerate(code_content):
                if char == '{':
                    if brace_count == 0:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start != -1:
                        json_str = code_content[json_start:i+1]
                        try:
                            return json.loads(json_str)
                        except:
                            pass
                        json_start = -1
            
            if json_start != -1:
                break
        
        # 方法3: 尝试查找 JSON 对象（使用括号匹配）
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(output):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = output[start_idx:i+1]
                    try:
                        return json.loads(json_str)
                    except:
                        pass
                    start_idx = -1
        
        # 如果括号未匹配（可能被截断），尝试补全
        if brace_count > 0 and start_idx != -1:
            incomplete_json = output[start_idx:]
            missing_braces = brace_count
            potential_json = incomplete_json + '}' * missing_braces
            try:
                result = json.loads(potential_json)
                pass
                return result
            except:
                pass
        
        return None
    
    def continue_execution_with_plugins(
        self,
        recommended_plugins: List[Dict[str, Any]],
        feedback_results: List[Dict[str, Any]],
        task_description: str,
        user_params: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        继续执行（用于分阶段执行，支持 action 机制）
        
        Args:
            recommended_plugins: 路由AI推荐的所有插件列表（用于保持系统提示词中的 PLUGINS_INFO）
            feedback_results: 前面步骤的执行结果
            task_description: 任务描述
            user_params: 用户提供的参数
            conversation_history: 对话历史（可选，如果不提供则使用 Agent 自己的历史）
            
        Returns:
            包含执行计划的字典，格式: {
                'success': bool,
                'action': str,     # 'call' 或 'finish'
                'calls': list,     # 工具调用列表（action='call' 时）
                'summary': str,    # 任务总结（action='finish' 时）
                'extracted_data': dict,  # 提取的数据（action='finish' 时）
                'error': str,      # 错误信息（如果失败）
                'ai_response': str  # AI 的原始响应
            }
        """
        from datetime import datetime
        
        # 格式化所有推荐插件的完整信息
        plugins_info_text = self._format_plugins_info(recommended_plugins)
        
        # 更新系统提示词（注入插件信息，保持历史记录）
        updated_prompt = self.system_prompt.replace('{PLUGINS_INFO}', plugins_info_text)
        self.update_system_prompt(updated_prompt)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_weekday = datetime.now().strftime("%A")
        
        # 清理 task_description，移除前面的 MCP 任务结果（只保留原始任务描述）
        # 因为在单个 MCP 任务的多步骤执行中，执行 AI 已经有历史对话，不需要重复传递前面的结果
        clean_task_description = task_description
        if "**前面已执行的MCP任务结果**" in task_description:
            # 提取原始任务描述（在"**前面已执行的MCP任务结果**"之前的部分）
            parts = task_description.split("**前面已执行的MCP任务结果**")
            if parts:
                clean_task_description = parts[0].strip()
        
        # 构建反馈文本
        user_params_text = json.dumps(user_params, ensure_ascii=False, indent=2) if user_params else '无'
        feedback_text = f"""[当前时间: {current_time} ({current_date} {current_weekday})]

前面步骤的执行结果：

{json.dumps(feedback_results, ensure_ascii=False, indent=2)}

请根据上述执行结果，分析并决定下一步操作：
- 如果还需要执行更多 MCP 工具调用（如处理结果、存储数据等），输出 action: "call" 和新的 calls 列表
- 如果所有调用已完成，任务已完成，输出 action: "finish" 和总结

当前任务描述: {clean_task_description}
用户提供的参数: {user_params_text}"""
        
        # 调用执行 AI（使用历史记录）
        response = self.chat(
            content=feedback_text,
            max_tokens=2000,
            temperature=0.3,
            use_history=True  # 使用历史记录，自动带上之前的对话
        )
        
        executor_output = response.get("content", "")
        
        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            return {
                'success': False,
                'action': None,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': f'工具执行 AI 继续生成失败: {error_msg}',
                'ai_response': executor_output
            }
        
        # 解析执行 AI 的输出
        parsed_result = self._parse_executor_output(executor_output)
        
        if not parsed_result:
            return {
                'success': False,
                'action': None,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': '无法解析继续生成的输出',
                'ai_response': executor_output
            }
        
        # 检查 action 字段
        action = parsed_result.get('action', 'call')  # 默认为 'call' 以保持向后兼容
        
        if action == 'finish':
            # 任务完成
            return {
                'success': True,
                'action': 'finish',
                'calls': None,
                'summary': parsed_result.get('summary', ''),
                'extracted_data': parsed_result.get('extracted_data', {}),
                'error': None,
                'ai_response': executor_output
            }
        elif action == 'call':
            # 需要继续执行新的 calls（统一使用数组格式）
            calls = parsed_result.get('calls', [])
            if not calls or not isinstance(calls, list):
                return {
                    'success': False,
                    'action': 'call',
                    'calls': None,
                    'summary': None,
                    'extracted_data': None,
                    'error': 'action 为 "call" 但缺少 calls 字段或格式错误（即使是单个调用，也必须使用 calls 数组格式）',
                    'ai_response': executor_output
                }
            
            return {
                'success': True,
                'action': 'call',
                'calls': calls,
                'summary': None,
                'extracted_data': None,
                'error': None,
                'ai_response': executor_output
            }
        else:
            return {
                'success': False,
                'action': action,
                'calls': None,
                'summary': None,
                'extracted_data': None,
                'error': f'未知的 action 类型: {action}',
                'ai_response': executor_output
            }
    
    def continue_execution(
        self,
        previous_messages: List[Dict[str, str]],
        feedback_results: List[Dict[str, Any]],
        task_description: str
    ) -> Dict[str, Any]:
        """
        继续执行（旧版本，保持向后兼容）
        
        Args:
            previous_messages: 之前的消息列表
            feedback_results: 前面步骤的执行结果
            task_description: 任务描述
            
        Returns:
            包含执行计划的字典
        """
        # 注意：这个方法已废弃，应该使用 continue_execution_with_plugins
        # 保留此方法仅用于向后兼容
        from datetime import datetime
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_weekday = datetime.now().strftime("%A")
        
        feedback_text = f"""[当前时间: {current_time} ({current_date} {current_weekday})]

前面步骤的执行结果：

{json.dumps(feedback_results, ensure_ascii=False, indent=2)}

请根据上述执行结果，继续生成后续步骤（包括当前需要等待的调用和后续所有调用）。
如果后续步骤需要使用前面步骤的结果，请从上述结果中提取相应的数据。
当前任务描述: {task_description}"""
        
        # 构建消息列表（包含之前的对话和新的反馈）
        messages = previous_messages + [{"role": "user", "content": feedback_text}]
        
        # 调用执行 AI
        response = self.chat_with_messages(
            messages=messages,
            max_tokens=2000,
            temperature=0.3,
            use_history=False
        )
        
        executor_output = response.get("content", "")
        
        if not response.get("success"):
            error_msg = response.get('message', '未知错误')
            return {
                'success': False,
                'tool': None,
                'input': None,
                'calls': None,
                'error': f'工具执行 AI 继续生成失败: {error_msg}',
                'ai_response': executor_output
            }
        
        # 解析执行 AI 的输出
        parsed_result = self._parse_executor_output(executor_output)
        
        if not parsed_result:
            return {
                'success': False,
                'tool': None,
                'input': None,
                'calls': None,
                'error': '无法解析继续生成的输出',
                'ai_response': executor_output
            }
        
        # 检查是否为批量调用格式
        if 'calls' in parsed_result and isinstance(parsed_result['calls'], list):
            return {
                'success': True,
                'tool': None,
                'input': None,
                'calls': parsed_result['calls'],
                'error': None,
                'ai_response': executor_output
            }
        else:
            # 单个调用格式（向后兼容）
            tool_method_name = parsed_result.get('tool')
            final_params = parsed_result.get('input', {})
            
            if not tool_method_name:
                return {
                    'success': False,
                    'tool': None,
                    'input': None,
                    'calls': None,
                    'error': '无法从继续生成的输出中解析工具方法名称',
                    'ai_response': executor_output
                }
            
            return {
                'success': True,
                'tool': tool_method_name,
                'input': final_params,
                'calls': None,
                'error': None,
                'ai_response': executor_output
            }

