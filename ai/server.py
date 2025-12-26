#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具集成 - HTTP REST API 服务器版本
提供 HTTP 接口用于对话和状态更新
"""

import os
import json
import uuid
import shutil
import queue
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from services.utils.mcp_client import MCPClientManager
from services.agents import (
    MainBrainAgent,
    SupervisorAgent,
    RouterAgent,
    ExecutorAgent,
    MemoryManagerAgent,
    MemoryRouterAgent,
    MemoryShardsAgent
)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量
mcp_client_manager = None
conversations_dir = Path(__file__).parent / "conversations"

# 会话管理器：为每个 history_file 维护独立的 AI 实例
session_agents = {}

# 任务状态队列：用于存储任务的状态更新
task_status_queues = {}


def init_mcp_manager():
    """初始化 MCP 客户端管理器"""
    global mcp_client_manager
    if mcp_client_manager is None:
        mcp_client_manager = MCPClientManager()
        mcp_client_manager.initialize_all()
    return mcp_client_manager


def get_agent_instances(history_file: str, status_callback=None):
    """
    根据 history_file 创建或获取 Agent 实例
    每个会话都有独立的 AI 实例，确保状态隔离
    """
    if history_file not in session_agents:
        # 创建新的 AI 实例组
        def chat_callback(agent_name: str, content: str):
            """通用聊天回调函数"""
            if status_callback:
                status_callback({
                    'type': 'agent_message',
                    'agent': agent_name,
                    'content': content
                })
            print(f"[{agent_name}] {content}")

        def stream_callback(agent_name: str, chunk_data: dict, accumulated_content: str):
            """流式传输回调函数"""
            if status_callback:
                status_callback({
                    'type': 'agent_stream',
                    'agent': agent_name,
                    'chunk': chunk_data.get('content', ''),
                    'accumulated': accumulated_content
                })
            print(f"[{agent_name}] {chunk_data.get('content', '')}")

        session_agents[history_file] = {
            'memory_manager': MemoryManagerAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'memory_router': MemoryRouterAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'memory_shards': MemoryShardsAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'main_brain': MainBrainAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'supervisor': SupervisorAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'router': RouterAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'executor': ExecutorAgent(
                provider='deepseek',
                history_file=history_file,
                chat_callback=chat_callback,
                stream_callback=stream_callback
            ),
            'last_main_brain_history_count': 0
        }
    
    return session_agents[history_file]


def call_tool(mcp_client_manager: MCPClientManager, call: dict) -> dict:
    """
    执行单个 MCP 工具调用
    
    Args:
        call: 工具调用字典，格式: {
            "tool": "工具方法名称",
            "input": {
                "参数名": "参数值"
            }
        }
        
    Returns:
        原始执行结果字典
    """
    tool_method_name = call.get('tool')
    final_params = call.get('input', {})
    
    if not tool_method_name:
        return {
            "success": False,
            "content": None,
            "error": "缺少工具方法名称"
        }
    
    tool_client = mcp_client_manager.get_client_for_tool(tool_method_name)
    if not tool_client:
        return {
            "success": False,
            "content": None,
            "error": "未找到工具客户端"
        }
    
    return tool_client.call_tool(tool_method_name, final_params)


def chat_with_status(input_text: str, history_file: str, status_queue: queue.Queue):
    """
    主要处理聊天函数，集成 main.py 的完整逻辑
    通过 status_queue 发送状态更新
    """
    # 初始化 MCP 管理器
    mcp_manager = init_mcp_manager()
    
    # 定义状态回调函数
    def emit_status(status_data):
        """发送状态更新到队列"""
        try:
            if isinstance(status_data, dict):
                status_queue.put(status_data)
                if status_data.get('type') == 'chat_callback':
                    print(f"[DEBUG] 发送 chat_callback: {status_data.get('callback_type')} - {status_data.get('content')[:50]}...")
        except Exception as e:
            print(f"[ERROR] 发送状态更新失败: {e}")
    
    # 获取该会话的 AI 实例
    agents = get_agent_instances(history_file, status_callback=emit_status)
    
    # 定义 chat_callback 函数，用于发送思考、回复、错误信息到前端
    def chat_callback(type: str, content: str):
        """通用聊天回调函数
        type 类型: thinking, reply, error
        content 输出内容
        """
        try:
            callback_data = {
                'type': 'chat_callback',
                'callback_type': type,  # thinking, reply, error
                'content': content
            }
            emit_status(callback_data)
            print(f"[{type}] {content}")
        except Exception as e:
            print(f"[ERROR] chat_callback 执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    try:
        # 步骤1: 记忆管理AI选择大纲
        selected_outlines = agents['memory_manager'].select_outlines(
            input_text, "主脑AI及监督AI"
        )
        main_brain_memory_mark = ""
        supervisor_memory_mark = ""
        chat_callback("thinking", f"读取到{len(selected_outlines)}条用户记忆索引")
        if selected_outlines:
            # 步骤2: 记忆路由AI选择payload路径并获取完整记忆数据
            main_brain_memory_data = agents['memory_router'].select_payload_paths(
                selected_outlines, input_text, "主脑AI"
            )
            if main_brain_memory_data:
                main_brain_memory_mark = agents['memory_router'].payload_to_markdown(
                    main_brain_memory_data
                )
            
            supervisor_memory_data = agents['memory_router'].select_payload_paths(
                selected_outlines, input_text, "监督AI"
            )
            if supervisor_memory_data:
                supervisor_memory_mark = agents['memory_router'].payload_to_markdown(
                    supervisor_memory_data
                )
        
        # 步骤3: 更新主脑和监督AI的用户记忆
        agents['main_brain'].update_user_memory(
            main_brain_memory_mark,
            mcp_manager.format_plugins_summary()
        )
        agents['supervisor'].update_user_memory(supervisor_memory_mark)
        
        # 步骤4: 调用主脑AI
        chat_callback("thinking", "正在思考..")
        agents['last_main_brain_history_count'] = agents['main_brain'].get_history_count()
        main_brain_json = agents['main_brain'].chat(
            content=input_text,
            max_tokens=1500,
            temperature=0.7,
            stream=False,
            stream_options={"include_usage": False}
        )
        
        # 验证顶层结构
        if "actions" not in main_brain_json:
            chat_callback("error", "ActionSpec JSON 格式错误，顶层必须包含 'actions' 字段")
            return None
        
        # 步骤5: 检查是否有MCP类型的action
        actions = main_brain_json.get("actions", [])
        has_mcp_action = any(action.get("type") == "task" for action in actions)
        
        # 步骤6: 如果有MCP action，调用监督AI
        if has_mcp_action:
            max_retries = 3
            supervisor_retry_count = 0
            current_main_brain_json = main_brain_json
            agents['supervisor'].clear_history()
            
            while supervisor_retry_count < max_retries:
                # 监督主脑 AI 的输出
                chat_callback("thinking", "正在监督MCP是否合理...")
                supervisor_decision = agents['supervisor'].supervise(
                    user_input=input_text,
                    main_brain_output=main_brain_json
                )
                
                # 如果监督通过，退出循环
                if supervisor_decision.get('decision') == 'APPROVE':
                    break
                
                # 如果监督驳回，且未达到最大重试次数
                if supervisor_decision.get('decision') == 'REJECT':
                    supervisor_retry_count += 1
                    reason = supervisor_decision.get('reason', '未知原因')
                    
                    # 如果已达到最大重试次数，警告但继续执行
                    if supervisor_retry_count >= max_retries:
                        break
                    
                    # 将反馈发送给主脑 AI 重新生成
                    chat_callback("thinking", "正在调整决策信息")
                    main_brain_json = agents['main_brain'].chat(
                        content=f"[监督反馈 - 第 {supervisor_retry_count} 次] {json.dumps(supervisor_decision, ensure_ascii=False)}\n\n请根据上述反馈，重新优化你的输出。",
                        max_tokens=1500,
                        temperature=0.7
                    )
                    
                    if not main_brain_json or "actions" not in main_brain_json:
                        chat_callback("error", "主脑 AI 重新生成的输出仍然无法解析")
                        return None
                    
                    actions = main_brain_json.get("actions", [])
                    has_mcp_action = any(action.get("type") == "task" for action in actions)
                    # 只有包含mcp类型的action时才继续循环，进行下一次监督
                    if not has_mcp_action:
                        break
                else:
                    # 未知的决策类型，默认放行
                    break
        
        if not main_brain_json:
            emit_status({
                'type': 'error',
                'message': '监督流程失败'
            })
            return None
        
        # 重新获取actions（监督后可能被修改）
        actions = main_brain_json.get("actions", [])
        
        # 步骤7: 执行MCP工具（如果有）
        target_plugins = []
        if has_mcp_action:
            chat_callback("thinking", "正在搜索MCP工具")
            router_result = agents['router'].find_plugins(
                task_description=main_brain_json,
                mcp_client_manager=mcp_manager
            )
            
            if not router_result['success']:
                chat_callback("error", f"工具路由搜索失败: {router_result.get('message', '未知错误')}")
                return None
            
            target_plugins = router_result['plugins']
        
        agents['executor'].clear_history()
        # 如果推荐插件能正常获取到,则执行MCP参数构建AI,将主脑AI的抽象层MCP任务描述具体实例化
        if len(target_plugins) > 0:
            chat_callback("thinking", "为MCP提供用户记忆信息")
            selected_outlines = agents['memory_manager'].select_outlines(
                input_text + '\n(以上为用户描述)\n' + json.dumps(actions, ensure_ascii=False) + '\n(以上为MCP任务需求)',
                "执行AI"
            )
            
            router_memory_mark = ""
            mcp_task_history = ""
            router_memory_data = agents['memory_router'].select_payload_paths(
                selected_outlines,
                input_text + '\n(以上为用户描述)\n' + json.dumps(actions, ensure_ascii=False) + '\n(以上为MCP任务需求)\n' + mcp_task_history,
                "执行AI"
            )
            if router_memory_data:
                router_memory_mark = agents['memory_router'].payload_to_markdown(router_memory_data)
            
            # 循环执行actions
            chat_callback("thinking", "正在执行MCP工具..")
            for i, action in enumerate(actions, 1):
                if action.get("type") == "task":
                    mcp_task_description = action.get("payload", "无任务/参数描述")
                    chat_callback("thinking", mcp_task_description)
                    mcp_task_result = agents['executor'].execute_plugins(
                        recommended_plugins=target_plugins,
                        memory_mark=router_memory_mark,
                        task_description=mcp_task_description,
                    )
                    
                    if not mcp_task_result['success']:
                        chat_callback("error", f"执行AI输出错误格式: {mcp_task_result.get('error', '未知错误')}")
                        return None
                    
                    if mcp_task_result['action'] == 'call':
                        # 按照执行AI输出的calls循环执行具体的MCP工具,并将所有结果拼接起来
                        tool_history = ""
                        j = 0
                        for call in mcp_task_result['calls']:
                            j += 1
                            tool_result = call_tool(mcp_manager, call)
                            
                            if tool_result['success']:
                                tool_history += call.get('tool') + "执行结果:\n" + json.dumps(tool_result['content'], ensure_ascii=False) + "\n"
                            else:
                                tool_history += call.get('tool') + "错误结果:\n" + tool_result.get('error', '未知错误') + "\n"
                                chat_callback("error", f"工具 {call.get('tool')} 执行失败: {tool_result.get('error', '未知错误')}")
                                return None
                        
                        mcp_task_history = json.dumps(tool_history, ensure_ascii=False) + "\n(上一轮MCP执行结果)"
            
            # 将所有MCP结果回传给主脑AI,并判断主脑AI的返回值是否为继续执行
            main_brain_json = agents['main_brain'].chat(
                content=mcp_task_history + '\n(以上为MCP执行结果)',
                max_tokens=1500,
                temperature=0.7
            )
            
            actions = main_brain_json.get("actions", [])
        
        # 步骤9: 循环检测actions里面的type如果有reply则直接输出AI的回复
        final_response = ""
        for act in actions:
            if act.get('type') == 'reply':
                reply_content = act.get('payload', '')
                chat_callback("reply", reply_content)
                final_response = reply_content
                
                # 记忆碎片增删改检测
                last_main_brain_history_json = json.dumps(
                    agents['main_brain'].get_history(
                        agents['main_brain'].get_history_count() - agents['last_main_brain_history_count']
                    ),
                    ensure_ascii=False
                )
                
                changes = agents['memory_shards'].detect_memory_changes(
                    main_brain_memory_mark,
                    last_main_brain_history_json
                )
                
                agents['last_main_brain_history_count'] = agents['main_brain'].get_history_count()
                agents['memory_shards'].apply_memory_changes(changes)
        
        return {
            'success': True,
            'response': final_response,
            'actions': actions
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        emit_status({
            'type': 'error',
            'message': f'处理对话失败: {str(e)}'
        })
        return None

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """创建新对话"""
    try:
        history_file = str(uuid.uuid4())
        conversations_dir.mkdir(parents=True, exist_ok=True)
        conversation_path = conversations_dir / history_file
        conversation_path.mkdir(parents=True, exist_ok=True)
        
        return jsonify({
            "success": True,
            "history_file": history_file,
            "message": "对话创建成功"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"创建对话失败: {str(e)}"
        }), 500


@app.route('/api/conversations', methods=['GET'])
def list_conversations():
    """获取历史对话列表"""
    try:
        conversations = []
        
        if not conversations_dir.exists():
            return jsonify({
                "success": True,
                "conversations": []
            })
        
        for item in conversations_dir.iterdir():
            if item.is_dir():
                history_file = item.name
                main_brain_session = item / "主脑ai.session"
                last_updated = None
                message_count = 0
                
                if main_brain_session.exists():
                    try:
                        last_updated = datetime.fromtimestamp(
                            main_brain_session.stat().st_mtime
                        ).strftime('%Y-%m-%d %H:%M:%S')
                        
                        with open(main_brain_session, 'r', encoding='utf-8') as f:
                            history_data = json.load(f)
                            if isinstance(history_data, list):
                                message_count = len(history_data)
                    except Exception:
                        pass
                
                conversations.append({
                    "history_file": history_file,
                    "last_updated": last_updated,
                    "message_count": message_count
                })
        
        conversations.sort(
            key=lambda x: x['last_updated'] or '',
            reverse=True
        )
        
        return jsonify({
            "success": True,
            "conversations": conversations
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"获取对话列表失败: {str(e)}"
        }), 500


@app.route('/api/conversations/<history_file>/history', methods=['GET'])
def get_conversation_history(history_file: str):
    """获取历史对话记录"""
    try:
        conversation_path = conversations_dir / history_file
        if not conversation_path.exists():
            return jsonify({
                "success": False,
                "message": f"对话 {history_file} 不存在"
            }), 404
        
        agents = get_agent_instances(history_file)
        main_brain_history = agents['main_brain'].get_history()
        
        return jsonify({
            "success": True,
            "history": main_brain_history,
            "message_count": len(main_brain_history)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"获取历史对话失败: {str(e)}"
        }), 500


@app.route('/api/conversations/<history_file>', methods=['DELETE'])
def delete_conversation(history_file: str):
    """删除对话记录"""
    try:
        conversation_path = conversations_dir / history_file
        
        if not conversation_path.exists():
            return jsonify({
                "success": False,
                "message": f"对话 {history_file} 不存在"
            }), 404
        
        # 删除对话目录
        shutil.rmtree(conversation_path)
        
        # 删除对应的记忆文件
        memory_file = Path(__file__).parent / ".memory" / f"{history_file}.json"
        if memory_file.exists():
            memory_file.unlink()
        
        # 清理会话中的AI实例
        if history_file in session_agents:
            del session_agents[history_file]
        
        return jsonify({
            "success": True,
            "message": "对话删除成功"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"删除对话失败: {str(e)}"
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "success": True,
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/chat', methods=['POST'])
def handle_chat():
    """处理聊天消息 - 使用 Server-Sent Events 推送状态更新"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求体必须为 JSON 格式'
            }), 400
        
        history_file = data.get('history_file')
        message = data.get('message')
        
        if not history_file or not message:
            return jsonify({
                'success': False,
                'message': '缺少必要参数: history_file 或 message'
            }), 400
        
        # 确保对话目录存在
        conversation_path = conversations_dir / history_file
        conversation_path.mkdir(parents=True, exist_ok=True)
        
        # 创建状态队列
        status_queue = queue.Queue()
        task_id = str(uuid.uuid4())
        task_status_queues[task_id] = status_queue
        
        def generate():
            """生成 Server-Sent Events 流"""
            try:
                # 在后台线程中执行聊天处理
                result_container = {'result': None, 'error': None}
                
                def run_chat():
                    try:
                        result = chat_with_status(message, history_file, status_queue)
                        result_container['result'] = result
                    except Exception as e:
                        result_container['error'] = str(e)
                        import traceback
                        traceback.print_exc()
                
                # 启动后台线程
                chat_thread = threading.Thread(target=run_chat)
                chat_thread.daemon = True
                chat_thread.start()
                
                # 发送状态更新
                while True:
                    try:
                        # 从队列获取状态更新，超时1秒
                        try:
                            status_data = status_queue.get(timeout=1)
                            # 发送 SSE 格式的数据
                            yield f"data: {json.dumps(status_data, ensure_ascii=False)}\n\n"
                            
                            # 如果是 reply 类型，表示处理完成
                            if (status_data.get('type') == 'chat_callback' and 
                                status_data.get('callback_type') == 'reply'):
                                break
                        except queue.Empty:
                            # 检查线程是否完成
                            if not chat_thread.is_alive():
                                break
                            continue
                    except Exception as e:
                        print(f"[ERROR] 发送状态更新失败: {e}")
                        break
                
                # 等待线程完成
                chat_thread.join(timeout=30)
                
                # 发送最终结果
                if result_container['error']:
                    yield f"data: {json.dumps({'type': 'error', 'message': result_container['error']}, ensure_ascii=False)}\n\n"
                elif result_container['result']:
                    if result_container['result'].get('success'):
                        yield f"data: {json.dumps({'type': 'response', 'data': result_container['result']}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': result_container['result'].get('message', '处理失败')}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': '处理超时'}, ensure_ascii=False)}\n\n"
                
            finally:
                # 清理任务队列
                if task_id in task_status_queues:
                    del task_status_queues[task_id]
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'处理消息失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    # 初始化 MCP 管理器
    print("正在初始化 MCP 客户端管理器...")
    init_mcp_manager()
    tools = mcp_client_manager.get_all_tools()
    print(f"✓ 已加载 {len(tools)} 个 MCP 工具")
    
    # 启动 Flask HTTP 服务器
    print("\n启动 HTTP REST API 服务器...")
    print("\nREST API 接口:")
    print("  POST   /api/chat - 发送消息（使用 SSE 推送状态更新）")
    print("  POST   /api/conversations - 创建对话")
    print("  GET    /api/conversations - 获取对话列表")
    print("  GET    /api/conversations/<history_file>/history - 获取历史对话")
    print("  DELETE /api/conversations/<history_file> - 删除对话")
    print("  GET    /api/health - 健康检查")
    print("\n服务器运行在: http://localhost:5001")
    
    app.run(host='0.0.0.0', port=5001, debug=True, threaded=True)
