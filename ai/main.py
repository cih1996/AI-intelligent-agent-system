#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具集成 - 主脑任务分发系统
主入口文件
"""

from datetime import datetime
import json
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


mcp_client_manager = None
history_file = "administrator"
last_main_brain_history_count = 0
def chat_callback(type: str, content: str):
    """通用聊天回调函数
        type 类型: thinking, reply
        content 输出内容
    """
    print(f"[{type}] {content}")

def stream_callback(agent_name: str, chunk_data: dict, accumulated_content: str):
    """流式传输回调函数"""
    pass
    #print(f"[{agent_name}] {chunk_data['content']}")
    #print(f"[{agent_name}] {accumulated_content}")


def call_tool(mcp_client_manager: MCPClientManager,call: dict) -> dict:
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
        原始执行结果字典，格式: {
            "success": bool,
            "content": Any,  # 执行成功时的结果内容
            "error": str,    # 执行失败时的错误信息
            ...
        }
    """      

    # 从 call 字典中提取工具名称和参数
    tool_method_name = call.get('tool')
    final_params = call.get('input', {})
    
    if not tool_method_name:
        return {
            "success": False,
            "content": None,
            "error": "缺少工具方法名称"
        }
    
    # 调用 MCP 工具
    
    tool_client = mcp_client_manager.get_client_for_tool(tool_method_name)
    if not tool_client:
        return {
            "success": False,
            "content": None,
            "error": "未找到工具客户端"
        }
    
    return tool_client.call_tool(tool_method_name, final_params)

# 记忆管理 AI Agent
memory_manager_agent = MemoryManagerAgent(provider='deepseek',history_file=history_file,stream_callback=stream_callback)

# 记忆路由 AI Router
memory_router_agent = MemoryRouterAgent(provider='deepseek', history_file=history_file,stream_callback=stream_callback)

# 记忆碎片 AI Shards
memory_shards_agent = MemoryShardsAgent(provider='deepseek', history_file=history_file,stream_callback=stream_callback)

# 主脑 AI Agent
main_brain_agent = MainBrainAgent(provider='deepseek',history_file=history_file,stream_callback=stream_callback)

# 监督 AI Agent
supervisor_agent = SupervisorAgent(provider='deepseek', history_file=history_file,stream_callback=stream_callback)

# 路由 AI Agent
router_agent = RouterAgent(provider='deepseek', history_file=history_file,stream_callback=stream_callback)

# 执行 AI Agent
executor_agent = ExecutorAgent(provider='deepseek', history_file=history_file,stream_callback=stream_callback)


def chat(input_text: str):
    """主要处理聊天函数"""

    # 记忆管理AI选择大纲
    selected_outlines = memory_manager_agent.select_outlines(input_text, "主脑AI及监督AI")
    main_brain_memory_mark = ""
    supervisor_memory_mark = ""
    chat_callback("thinking",f"读取到{len(selected_outlines)}条用户记忆索引")
    if selected_outlines:
        # 记忆路由AI选择payload路径并获取完整记忆数据
        main_brain_memory_data = memory_router_agent.select_payload_paths(selected_outlines, input_text, "主脑AI")
        if main_brain_memory_data:
            main_brain_memory_mark = memory_router_agent.payload_to_markdown(main_brain_memory_data)
        
        # 记忆路由AI选择payload路径并获取完整记忆数据
        supervisor_memory_data = memory_router_agent.select_payload_paths(selected_outlines, input_text, "监督AI")
        if supervisor_memory_data:
            supervisor_memory_mark = memory_router_agent.payload_to_markdown(supervisor_memory_data)
    
    
    #print("主脑AI记忆数据:\n", main_brain_memory_mark)
    #print("监督AI记忆数据:\n", supervisor_memory_mark)
 
    # 在每次调用主脑AI前，重新加载用户记忆并更新系统提示词
    main_brain_agent.update_user_memory(main_brain_memory_mark,mcp_client_manager.format_plugins_summary())
    supervisor_agent.update_user_memory(supervisor_memory_mark)
  
    # 调用主脑AI
    chat_callback("thinking","正在思考..")
    last_main_brain_history_count = main_brain_agent.get_history_count()
    main_brain_json = main_brain_agent.chat(
        content=input_text,
        max_tokens=1500,
        temperature=0.7,
        stream=False,
        stream_options={"include_usage": False}
    )

    # 验证顶层结构
    if "actions" not in main_brain_json:
        chat_callback("error","ActionSpec JSON 格式错误，顶层必须包含 'actions' 字段")
        return


    # 格式化并输出主脑AI的输出（文本格式，用于显示解析后的行动计划）
    #formatted_output = format_main_brain_output(main_brain_json)
    #if formatted_output.strip():
    #    print(f"\n📋 [行动计划] {formatted_output}")
    
    # 检查actions中是否包含mcp类型的action
    actions = main_brain_json.get("actions", [])
    has_mcp_action = any(action.get("type") == "task" for action in actions)
    
    # 调用监督AI
    if has_mcp_action:
        # 最多重复监督次数
        max_retries = 3
        supervisor_retry_count = 0
        # 是否放行
        current_main_brain_json = main_brain_json
        supervisor_agent.clear_history()
        while supervisor_retry_count < max_retries:
            # 监督主脑 AI 的输出
            chat_callback("thinking","正在监督MCP是否合理...")
            supervisor_decision = supervisor_agent.supervise(
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

                #print(f"⚠ [监督AI] 拒绝（第 {supervisor_retry_count}/{max_retries} 次）: {reason}")
       
                
                # 如果已达到最大重试次数，警告但继续执行
                if supervisor_retry_count >= max_retries:
                    #print(f"⚠ [监督AI] 已达到最大重试次数，将使用当前输出继续执行")
                    break
                

                # 将反馈发送给主脑 AI 重新生成
                chat_callback("thinking","正在调整决策信息")
                main_brain_json = main_brain_agent.chat(
                    content=f"[监督反馈 - 第 {supervisor_retry_count} 次] {json.dumps(supervisor_decision, ensure_ascii=False)}\n\n请根据上述反馈，重新优化你的输出。",
                    max_tokens=1500,
                    temperature=0.7
                )
      
                if not current_main_brain_json or "actions" not in current_main_brain_json:
                    print("\n✗ 错误: 主脑 AI 重新生成的输出仍然无法解析")
                    return None, ""
                
                # 格式化并输出重新生成的结果
                # retry_formatted = format_main_brain_output(current_main_brain_json)
                print(f"🔄 [主脑AI] 重新生成 ({supervisor_retry_count}): {current_main_brain_json}")
                actions = current_main_brain_json.get("actions", [])
                has_mcp_action = any(action.get("type") == "task" for action in actions)
                # 只有包含mcp类型的action时才继续循环，进行下一次监督
                if not has_mcp_action:
                    break

            else:
                # 未知的决策类型，默认放行
                print(f"\n⚠ 警告: 未知的监督决策类型，默认放行")
                break
        
   
        if not main_brain_json:
            print("\n✗ 错误: 监督流程失败")
            return
        
        # 重新获取actions（监督后可能被修改）
        actions = main_brain_json.get("actions", [])
    
    # 执行MCP AI(经过监督AI审核后,重新判断是否需要MCP工具执行)
    target_plugins = []
    if has_mcp_action:
        chat_callback("thinking","正在搜索MCP工具")
        router_result = router_agent.find_plugins(
            task_description=main_brain_json,
            mcp_client_manager=mcp_client_manager
        )
        
        if not router_result['success']:
            print(f"✗ 工具路由搜索失败: {router_result.get('message', '未知错误')}")
            return 
        
        target_plugins = router_result['plugins']
        print(f"✓ 推荐插件 ({len(target_plugins)} 个):")
        for i, plugin in enumerate(target_plugins, 1):
            print(f"  {i}. {plugin['name']} - {plugin.get('description', '')}")

    executor_agent.clear_history()
    # 如果推荐插件能正常获取到,则执行MCP参数构建AI,将主脑AI的抽象层MCP任务描述具体实例化
    if len(target_plugins)>0:
        chat_callback("thinking","为MCP提供用户记忆信息")
        selected_outlines = memory_manager_agent.select_outlines(input_text+'\n(以上为用户描述)\n'+json.dumps(actions, ensure_ascii=False)+')\n(以上为MCP任务需求)', "执行AI")
        print("[记忆AI] 即将执行MCP工具,下面是用户需求及任务描述,由记忆AI挑选合适的记忆数据")
        print(input_text+'(以上为用户描述\n'+json.dumps(actions, ensure_ascii=False)+')\n以上为MCP任务需求')
        router_memory_mark = ""
        mcp_task_history = ""
        router_memory_data = memory_router_agent.select_payload_paths(selected_outlines,input_text+'\n(以上为用户描述)\n'+json.dumps(actions, ensure_ascii=False)+')\n(以上为MCP任务需求)\n'+mcp_task_history, "执行AI")
        if router_memory_data:
            router_memory_mark = memory_router_agent.payload_to_markdown(router_memory_data)
        # 循环执行actions
        chat_callback("thinking","正在执行MCP工具..")
        for i, action in enumerate(actions, 1):
            if action.get("type") == "task":
                #print(f"[执行AI] 正在将主脑的第{i}个MCP任务描述具体实例化")
                print(action)
                mcp_task_description = action.get("payload", "无任务/参数描述")
                chat_callback("thinking",mcp_task_description)
                mcp_task_result = executor_agent.execute_plugins(
                    recommended_plugins=target_plugins,
                    memory_mark=router_memory_mark,
                    task_description=mcp_task_description,
                )


                if not mcp_task_result['success']:
                    print(f"✗ 执行AI输出错误格式: {mcp_task_result.get('error', '未知错误')}")
                    return
                
                if mcp_task_result['action'] == 'call':
                    # 按照执行AI输出的calls循环执行具体的MCP工具,并将所有结果拼接起来
                    tool_history = ""
                    j = 0
                    for call in mcp_task_result['calls']:
     
                        print("tool ["+call.get("tool")+"] 执行参数:",call)
                        j += 1
                        tool_result = call_tool(mcp_client_manager,call)
                        #print("原始tool ["+call.get("tool")+"] 执行结果数据:",tool_result)
                        if tool_result['success']:
                            tool_history +=call.get('tool') + "执行结果:\n" + json.dumps(tool_result['content'], ensure_ascii=False)+"\n"
                        else:
                            tool_history += call.get('tool') + "错误结果:\n" + tool_result.get('error', '未知错误')+"\n"
                            return

                    mcp_task_history = json.dumps(tool_history, ensure_ascii=False)+"\n(上一轮MCP执行结果)"
                    print(mcp_task_history)
        
        # 将所有MCP结果回传给主脑AI,并判断主脑AI的返回值是否为继续执行
        main_brain_json = main_brain_agent.chat(
            content=mcp_task_history+'\n(以上为MCP执行结果)',
            max_tokens=1500,
            temperature=0.7
        )

        actions = main_brain_json.get("actions", [])

        
    # 循环检测actions里面的type如果有reply则直接输出AI的回复
    for act in actions:
        if act.get('type') == 'reply':
            reply_content = act.get('payload', '')
            chat_callback("reply",reply_content)
            last_main_brain_history_json = json.dumps(
            main_brain_agent.get_history(main_brain_agent.get_history_count() - last_main_brain_history_count),
                ensure_ascii=False
            )
            print('='*100)
            print("开始执行记忆碎片增删改检测AI,以下是原始的AI对话历史完整片段")
            print(last_main_brain_history_json)
            print('='*100)
            changes = memory_shards_agent.detect_memory_changes(main_brain_memory_mark,last_main_brain_history_json)
            last_main_brain_history_count = main_brain_agent.get_history_count()
            memory_shards_agent.apply_memory_changes(changes)
        

    
   
    #print(json.dumps(changes, ensure_ascii=False))
    #print('='*100)
    

   
def main():
    """主函数"""
    global mcp_client_manager
  
    # 初始化 MCP 客户端管理器（从 mcp.json 读取配置）
    mcp_client_manager = MCPClientManager()
    mcp_client_manager.initialize_all()


    # 获取所有工具定义
    tools = mcp_client_manager.get_all_tools()
    print(f"  ✓ 已加载 {len(tools)} 个 MCP 工具")

    # 交互循环
    conversation_count = 0
    while True:
        try:
            # 获取用户输入
            user_input = input("\n你: ").strip()
            
            if not user_input:
                continue
            
            # 处理特殊命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n再见！")
                break
         
            # 发送消息给主脑 AI
            conversation_count += 1
            chat(user_input)
        except KeyboardInterrupt:
            print("\n\n程序被用户中断")
            break
        except Exception as e:
            print(f"\n✗ 发生错误: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

