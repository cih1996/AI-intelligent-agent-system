#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
核心业务逻辑
处理 MCP 工具执行、任务分发等核心功能
"""

import json
import re
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from services.utils.mcp_client import MCPClientManager
from services.agents import (
    MainBrainAgent,
    SupervisorAgent,
    RouterAgent,
    ExecutorAgent,
    MemoryManagerAgent
)



def format_main_brain_output(json_data: Dict[str, Any]) -> str:
    """
    将主脑AI的JSON输出格式化为易读的文本
    
    Args:
        json_data: 主脑AI的JSON输出
        
    Returns:
        格式化后的文本
    """
    if not json_data or "actions" not in json_data:
        return "无有效输出"
    
    actions = json_data.get("actions", [])
    if not actions:
        return "无操作"
    
    lines = []
    for i, action in enumerate(actions, 1):
        action_type = action.get("type", "unknown")
        payload = action.get("payload", {})
        
        if action_type == "reply":
            content = payload.get("content", "")
            lines.append(f"📝 回复: {content}")
        elif action_type == "mcp":
            description = payload.get("description", "")
            params = payload.get("parameters", {})
            lines.append(f"🔧 MCP任务: {description}")
            if params:
                params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                lines.append(f"   参数: {params_str}")
        elif action_type == "update_memory":
            lines.append(f"🧠 记忆更新: 更新用户记忆库")
        else:
            lines.append(f"❓ 未知操作类型: {action_type}")
    
    return "\n".join(lines)




def process_single_mcp_action(
    router_agent: RouterAgent,
    mcp_client_manager: MCPClientManager,
    action: Dict[str, Any],
    executor_agent: ExecutorAgent,
    previous_mcp_results: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    处理单个MCP action
    
    每次调用时都会创建新的 ExecutorAgent 实例，确保提示词初始化一次，
    并且包含可执行的 MCP 插件信息。
    
    Args:
        router_agent: 路由AI Agent实例
        mcp_client_manager: MCPClientManager 实例
        action: MCP action 字典
        executor_agent: 执行AI Agent实例
        previous_mcp_results: 前面已执行的MCP任务结果列表，用于传递给决策AI
        
    Returns:
        执行结果字典
    """
    description = action.get("payload", {}).get("description", "")
    provided_params = action.get("payload", {}).get("parameters", {})
    
    original_description = description
    
    # 如果有前面的MCP结果，将其添加到任务描述中，让决策AI能够看到前面的结果
    enhanced_description = description
    if previous_mcp_results:
        previous_results_text = "\n\n**前面已执行的MCP任务结果**（你可以使用这些结果来完成当前任务）:\n"
        for idx, prev_result in enumerate(previous_mcp_results, 1):
            prev_desc = prev_result.get('description', '未知任务')
            prev_summary = prev_result.get('summary', '')
            prev_extracted = prev_result.get('extracted_data', {})
            prev_result_data = prev_result.get('result')
            
            previous_results_text += f"\n--- 任务 {idx}: {prev_desc} ---\n"
            
            # 优先使用 summary 和 extracted_data（更简洁）
            if prev_summary:
                previous_results_text += f"总结: {prev_summary}\n"
            if prev_extracted:
                previous_results_text += f"提取的关键数据:\n{json.dumps(prev_extracted, ensure_ascii=False, indent=2)}\n"
            
            # 如果没有 summary，则使用 result 数据
            if not prev_summary and prev_result_data:
                # 如果是批量执行结果，提取关键信息
                if isinstance(prev_result_data, dict) and 'results' in prev_result_data:
                    results_list = prev_result_data.get('results', [])
                    success_count = prev_result_data.get('success_count', 0)
                    total_count = prev_result_data.get('total', len(results_list))
                    previous_results_text += f"执行了 {total_count} 个工具调用，{success_count} 个成功\n"
                    
                    # 只显示成功的结果的关键信息
                    for j, r in enumerate(results_list, 1):
                        if r.get('success'):
                            tool_name = r.get('tool', '')
                            result_data = r.get('result')
                            if isinstance(result_data, dict):
                                # 提取关键字段
                                key_info = []
                                for key in ['id', 'key', 'message', 'count', 'success']:
                                    if key in result_data:
                                        key_info.append(f"{key}={result_data[key]}")
                                if key_info:
                                    previous_results_text += f"  ✓ {tool_name}: {', '.join(key_info)}\n"
                                else:
                                    previous_results_text += f"  ✓ {tool_name}: 执行成功\n"
                            else:
                                previous_results_text += f"  ✓ {tool_name}: 执行成功\n"
                else:
                    # 单个结果，显示关键信息
                    if isinstance(prev_result_data, dict):
                        key_info = []
                        for key in ['id', 'key', 'message', 'count', 'success', 'url', 'title']:
                            if key in prev_result_data:
                                key_info.append(f"{key}={prev_result_data[key]}")
                        if key_info:
                            previous_results_text += f"结果: {', '.join(key_info)}\n"
                        else:
                            previous_results_text += f"结果: {json.dumps(prev_result_data, ensure_ascii=False)}\n"
                    else:
                        previous_results_text += f"结果: {str(prev_result_data)[:200]}...\n" if len(str(prev_result_data)) > 200 else f"结果: {prev_result_data}\n"
        
        # 将前面的结果添加到任务描述中（只用于 execute_task）
        enhanced_description = f"{description}{previous_results_text}"
        
        # 打印时只显示原始描述，避免输出过长
        print(f"\n🔧 [MCP执行] {original_description}")
        print(f"📋 [上下文] 已加载 {len(previous_mcp_results)} 个前面MCP任务的结果")
    else:
        print(f"\n🔧 [MCP执行] {description}")
    
    if not description:
        print("\n✗ 错误: 缺少任务描述")
        return {
            "success": False,
            "description": original_description,
            "error": "缺少任务描述"
        }
    
    # 步骤 1: 使用工具路由 AI 查找合适的 MCP 工具插件
    # 使用 original_description 进行路由搜索（不包含前面结果信息）

    router_result = router_agent.find_plugins(
        task_description=original_description,
        mcp_client_manager=mcp_client_manager
    )
    
    if not router_result['success']:
        print(f"✗ 工具路由搜索失败: {router_result.get('message', '未知错误')}")
        return {
            "success": False,
            "description": original_description,
            "error": f"工具路由搜索失败: {router_result.get('message', '未知错误')}"
        }
    
    recommended_plugins = router_result['plugins']
    
    print(f"✓ 推荐插件 ({len(recommended_plugins)} 个):")
    for i, plugin in enumerate(recommended_plugins, 1):
        print(f"  {i}. {plugin['name']} - {plugin.get('description', '')}")
    print()
    

    # 步骤 3: 使用工具执行 AI 选择具体方法并执行 MCP 工具
    # 使用 enhanced_description（包含前面结果信息）传递给 execute_plugins
    execute_result = executor_agent.execute_plugins(
        recommended_plugins=recommended_plugins,
        task_description=enhanced_description,  # 使用增强后的描述（包含前面结果）
        user_params=provided_params
    )
    
    if execute_result['success']:
        # 检查 action 字段
        action = execute_result.get('action', 'call')  # 默认为 'call' 以保持向后兼容
        
        if action == 'finish':
            # 任务完成，返回总结
            return {
                "success": True,
                "description": original_description,  # 返回原始描述
                "action": "finish",
                "summary": execute_result.get('summary', ''),
                "extracted_data": execute_result.get('extracted_data', {})
            }
        elif action == 'call':
            # 需要执行工具调用（统一使用 calls 数组格式）
            if execute_result.get('calls'):
                # 使用 calls 数组（即使是单个调用，也使用数组格式）
                return execute_batch_calls_with_stages(
                    executor_agent=executor_agent,
                    mcp_client_manager=mcp_client_manager,
                    recommended_plugins=recommended_plugins,
                    initial_calls=execute_result['calls'],
                    task_description=original_description,  # 使用原始描述（不包含前面结果）
                    user_params=provided_params
                )
            else:
                return {
                    "success": False,
                    "description": original_description,
                    "error": "执行结果格式错误：action 为 'call' 但缺少 calls 字段（即使是单个调用，也必须使用 calls 数组格式）"
                }
        else:
            return {
                "success": False,
                "description": original_description,
                "error": f"未知的 action 类型: {action}"
            }
    else:
        print(f"✗ 工具执行失败: {execute_result.get('error', '未知错误')}")
        return {
            "success": False,
            "description": original_description,
            "error": execute_result.get('error', '未知错误')
        }


def execute_batch_calls_with_stages(
    executor_agent: ExecutorAgent,
    mcp_client_manager: MCPClientManager,
    recommended_plugins: List[Dict[str, Any]],
    initial_calls: List[Dict[str, Any]],
    task_description: str,
    user_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    执行批量调用，支持 action 机制
    
    执行流程说明：
    ============
    1. 初始执行：
       - 执行初始的 calls 列表
       - 收集所有执行结果
    
    2. 反馈循环：
       - 将执行结果反馈给 executor_agent
       - executor_agent 分析结果，输出 action:
         - action: "call" → 继续执行新的 calls 列表
         - action: "finish" → 完成任务，返回总结
       - 如果 action 是 "call"，继续执行新的 calls，重复步骤 2
       - 如果 action 是 "finish"，返回总结和提取的数据
    
    历史对话处理说明：
    ===============
    - 系统提示词：每次调用 executor_agent 时，都会使用包含 {PLUGINS_INFO} 的完整系统提示词
    - 对话历史：每次反馈时，会将之前的对话和执行结果一起传递给 AI
    - 反馈结果：每次都会添加新的执行结果，作为新的上下文传递给 AI
    - 上下文累积：AI 能看到完整的对话历史和所有之前的执行结果，做出更准确的决策
    
    Args:
        executor_agent: 执行AI Agent实例
        mcp_client_manager: MCPClientManager 实例
        recommended_plugins: 推荐的插件列表（用于保持系统提示词中的 PLUGINS_INFO）
        initial_calls: 初始调用列表
        task_description: 任务描述
        user_params: 用户提供的参数
        
    Returns:
        包含执行结果的字典
    """

    
    # ==================== 初始化状态 ====================
    all_results = []  # 保存所有执行结果
    current_stage = 1
    max_stages = 10
    current_calls = initial_calls  # 当前需要执行的调用列表
    
    print(f"⚙️  [批量执行] 初始共 {len(current_calls)} 个调用")
    
    # ==================== 主循环：执行 -> 反馈 -> 继续执行 ====================
    while current_stage <= max_stages:
        # 步骤 1: 执行当前 calls 列表中的所有调用
        print(f"\n📋 [阶段 {current_stage}] 执行 {len(current_calls)} 个调用...")
        
        stage_results = []
        all_success = True
        
        for idx, call in enumerate(current_calls, 1):
            tool_method_name = call.get('tool')
            final_params = call.get('input', {})
            
            if not tool_method_name:
                print(f"  ✗ [{idx}] 缺少工具方法名称")
                stage_results.append({
                    'success': False,
                    'tool': None,
                    'result': None,
                    'error': '缺少工具方法名称'
                })
                all_success = False
                continue
            
            print(f"  → [{idx}] {tool_method_name}")
            print(f"     [MCP] 参数: {final_params}")
            
            tool_result = mcp_client_manager.call_tool(tool_method_name, final_params)
            
            if tool_result["success"]:
                print(f"     ✓ 成功")
                stage_results.append({
                    'success': True,
                    'tool': tool_method_name,
                    'result': tool_result['content'],
                    'error': None
                })
            else:
                print(f"     ✗ 失败: {tool_result.get('error', '未知错误')}")
                stage_results.append({
                    'success': False,
                    'tool': tool_method_name,
                    'result': None,
                    'error': tool_result.get('error', '未知错误')
                })
                all_success = False
        
        # 将本次执行结果添加到总结果中
        all_results.extend(stage_results)
        
        # 步骤 2: 将执行结果反馈给 executor_agent
        print(f"\n  📤 [阶段 {current_stage}] 反馈执行结果给决策AI...")
        
        # 准备反馈结果
        feedback_results = []
        for idx, result in enumerate(stage_results, 1):
            if result['success']:
                feedback_results.append({
                    'step': idx,
                    'tool': result['tool'],
                    'result': result['result']
                })
            else:
                feedback_results.append({
                    'step': idx,
                    'tool': result['tool'],
                    'error': result['error']
                })
    
        
        # 调用 executor_agent 继续执行（使用包含 PLUGINS_INFO 的完整系统提示词）
        continue_result = executor_agent.continue_execute_plugins(
            recommended_plugins=recommended_plugins,
            feedback_results=feedback_results,
            task_description=task_description,
            user_params=user_params
        )
        
        if not continue_result.get('success'):
            print(f"  ✗ 决策AI处理失败: {continue_result.get('error', '未知错误')}")
            return {
                "success": False,
                "description": task_description,
                "error": f"决策AI处理失败: {continue_result.get('error', '未知错误')}",
                "result": {
                    'total': len(all_results),
                    'success_count': sum(1 for r in all_results if r['success']),
                    'failed_count': sum(1 for r in all_results if not r['success']),
                    'results': all_results
                }
            }
        
        # 检查 action 字段
        action = continue_result.get('action', 'call')
        
        if action == 'finish':
            # 任务完成，返回总结
            print(f"\n✅ [阶段 {current_stage}] 任务完成")
            print(f"📝 总结: {continue_result.get('summary', '')}")
            
            success_count = sum(1 for r in all_results if r['success'])
            return {
                "success": True,
                "description": task_description,
                "action": "finish",
                "summary": continue_result.get('summary', ''),
                "extracted_data": continue_result.get('extracted_data', {}),
                "result": {
                    'total': len(all_results),
                    'success_count': success_count,
                    'failed_count': len(all_results) - success_count,
                    'results': all_results
                }
            }
        elif action == 'call':
            # 需要继续执行新的 calls（统一使用数组格式）
            new_calls = continue_result.get('calls')
            
            if new_calls and isinstance(new_calls, list):
                # 使用 calls 数组（即使是单个调用，也使用数组格式）
                current_calls = new_calls
                print(f"\n  ↻ [阶段 {current_stage}] 决策AI要求继续执行 {len(current_calls)} 个新调用")
            
                current_stage += 1
                continue
            else:
                print(f"  ⚠ action 为 'call' 但缺少 calls 字段或格式错误，任务结束")
                success_count = sum(1 for r in all_results if r['success'])
                return {
                    "success": all_success,
                    "description": task_description,
                    "error": "action 为 'call' 但缺少 calls 字段或格式错误（即使是单个调用，也必须使用 calls 数组格式）",
                    "result": {
                        'total': len(all_results),
                        'success_count': success_count,
                        'failed_count': len(all_results) - success_count,
                        'results': all_results
                    }
                }
        else:
            print(f"  ⚠ 未知的 action 类型: {action}，任务结束")
            success_count = sum(1 for r in all_results if r['success'])
            return {
                "success": False,
                "description": task_description,
                "error": f"未知的 action 类型: {action}",
                "result": {
                    'total': len(all_results),
                    'success_count': success_count,
                    'failed_count': len(all_results) - success_count,
                    'results': all_results
                }
            }
    
    # 达到最大阶段数，返回当前结果
    print(f"\n⚠️  达到最大阶段数 ({max_stages})，任务结束")
    success_count = sum(1 for r in all_results if r['success'])
    return {
        "success": all_success,
        "description": task_description,
        "error": f"达到最大阶段数 ({max_stages})",
        "result": {
            'total': len(all_results),
            'success_count': success_count,
            'failed_count': len(all_results) - success_count,
            'results': all_results
        }
    }


def process_actions_loop(
    main_brain_agent: MainBrainAgent,
    router_agent: RouterAgent,
    memory_manager_agent: MemoryManagerAgent,
    supervisor_agent: SupervisorAgent,
    mcp_client_manager: MCPClientManager,
    executor_agent: ExecutorAgent,
    actions: List[Dict[str, Any]],
    max_iterations: int = 10,
    current_user_input: str = None,
    current_ai_output: str = None
):
    """
    循环处理主脑AI提供的抽象actions,包含mcp

    Args:
        main_brain_agent: 主脑AI Agent实例
        router_agent: 路由AI Agent实例
        memory_manager_agent: 记忆管理AI Agent实例
        supervisor_agent: 监督AI Agent实例 （可选，用于记忆更新
        mcp_client_manager: MCPClientManager 实例
        executor_agent: 执行AI Agent实例
        actions: actions 数组
        max_iterations: 最大迭代次数
        current_user_input: 当前轮次的用户输入（可选，用于记忆更新）
        current_ai_output: 当前轮次的AI输出（可选，用于记忆更新）
    """
    iteration = 0
    last_mcp_result = None  # 只保存最后一次MCP任务的结果（用于递归总结）
    
    while iteration < max_iterations:
        iteration += 1
        
        # 检查是否有 MCP 类型的 action
        has_mcp_action = any(
            action.get("type") == "mcp" 
            for action in actions
        )
        
        # 如果没有 MCP action，处理 reply 和 update_memory 并退出循环
        if not has_mcp_action:
            for action in actions:
                action_type = action.get("type")
                payload = action.get("payload", {})
                
                if action_type == "reply":
                    content = payload.get("content", "")
                    print(f"\nAI: {content}")
                elif action_type == "update_memory":
                    print(f"\n🧠 [记忆管理] 开始更新用户记忆...")
                    
                    user_input = payload.get("user_input", "") or current_user_input or ""
                    ai_output = payload.get("ai_output", "") or current_ai_output or ""
                    
                    # 调用记忆管理AI（内部会自动加载和保存记忆）
                    updated_memory = memory_manager_agent.update_memory(
                        user_input=user_input or "（无用户输入）",
                        ai_output=ai_output or "（无AI输出）"
                    )
                    
                    # 更新主脑AI和监督AI的系统提示词
                    main_brain_agent.update_user_memory(updated_memory,mcp_client_manager.format_plugins_summary())
                    supervisor_agent.update_user_memory(updated_memory)
                    print(f"✓ 记忆更新完成")
            break
        
        # 处理当前 actions 数组
        mcp_results = []
        
        for i, action in enumerate(actions, 1):
            action_type = action.get("type")
            payload = action.get("payload", {})
            
            if action_type == "reply":
                pass  # 在还有 MCP 的情况下，先不输出 reply
            
            elif action_type == "update_memory":
                print(f"\n🧠 [记忆管理] 开始更新用户记忆...")
                
                user_input = payload.get("user_input", "") or current_user_input or ""
                ai_output = payload.get("ai_output", "") or current_ai_output or ""
    
                
                # 调用记忆管理AI（内部会自动加载和保存记忆）
                updated_memory = memory_manager_agent.update_memory(
                    user_input=user_input or "（无用户输入）",
                    ai_output=ai_output or "（无AI输出）"
                )
                
                # 更新主脑AI的系统提示词
                main_brain_agent.update_user_memory(updated_memory,mcp_client_manager.format_plugins_summary())
                supervisor_agent.update_user_memory(updated_memory)
                print(f"✓ 记忆更新完成")
            
            elif action_type == "mcp":
                # 只传递最后一次MCP任务的结果（不累积所有结果）
                # 这样执行AI可以基于上一个任务的结果进行递归总结
                previous_mcp_results = [last_mcp_result] if last_mcp_result else []
                
                result = process_single_mcp_action(
                    router_agent=router_agent,
                    mcp_client_manager=mcp_client_manager,
                    action=action,
                    executor_agent=executor_agent,
                    previous_mcp_results=previous_mcp_results  # 只传递最后一次结果
                )
                mcp_results.append(result)
                
                # 只保留最后一次MCP任务的结果（替换之前的结果，不累积）
                if result.get('success'):
                    last_mcp_result = {
                        'description': result.get('description', ''),
                        'result': result.get('result'),
                        'summary': result.get('summary'),
                        'extracted_data': result.get('extracted_data')
                    }
            
            else:
                print(f"\n✗ 未知的 action 类型: {action_type}")
        
        # 如果没有 MCP 结果，退出循环
        if not mcp_results:
            break
        
        # 构建反馈消息（只返回最终执行报告，不包含详细执行流程）
        feedback_parts = []
        feedback_parts.append("[MCP 执行结果]")
        
        # 只返回最后一个MCP任务的最终报告（summary和extracted_data）
        # 前面的任务结果只用于执行AI的递归总结，不反馈给主脑AI
        last_result = mcp_results[-1]  # 只取最后一个结果
        
        if last_result.get('success'):
            # 如果任务完成（action: "finish"），返回总结和提取的数据
            if last_result.get('action') == 'finish':
                summary = last_result.get('summary', '')
                extracted_data = last_result.get('extracted_data', {})
                
                if summary:
                    feedback_parts.append(f"\n执行总结: {summary}")
                
                if extracted_data:
                    feedback_parts.append(f"\n提取的关键数据:")
                    feedback_parts.append(json.dumps(extracted_data, ensure_ascii=False, indent=2))
            else:
                # 如果还在执行中，只返回简要状态
                feedback_parts.append(f"\n任务: {last_result.get('description', '未知')}")
                feedback_parts.append(f"状态: 执行中")
        else:
            # 执行失败
            feedback_parts.append(f"\n任务: {last_result.get('description', '未知')}")
            feedback_parts.append(f"状态: 失败")
            feedback_parts.append(f"错误: {last_result.get('error', '未知错误')}")
        
        feedback_message = "\n".join(feedback_parts)
        
        print(f"\n📤 [反馈] 向主脑AI反馈MCP执行结果")
        
     
        # 将 MCP 执行结果反馈给主脑 AI
        response = main_brain_agent.chat(
            content=feedback_message,
            max_tokens=1500,
            temperature=0.7
        )
        
        if not response.get("success"):
            print(f"\n✗ 错误: {response.get('message', '未知错误')}")
            break
        
        ai_response = response["content"]
        
        # 解析主脑输出的 ActionSpec JSON
        main_brain_json = parse_main_brain_json(ai_response)
        
        if not main_brain_json:
            print("\n✗ 错误: 无法解析主脑输出的 JSON 格式")
            break
        
        # 验证顶层结构
        if "actions" not in main_brain_json:
            print("\n✗ 错误: ActionSpec JSON 格式错误")
            break
        
        # 格式化并输出主脑AI的输出
        formatted_output = format_main_brain_output(main_brain_json)
        print(f"\n🧠 [主脑AI] {formatted_output}")
        
        # 更新 actions 数组，继续循环
        actions = main_brain_json.get("actions", [])
        
        if not actions:
            print("\n✓ 主脑 AI 已完成所有任务，无更多 actions")
            break

