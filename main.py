#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具集成 - 主脑任务分发系统
主入口文件
"""

from datetime import datetime
from utils.mcp_client import MCPClientManager
from ai_agents import (
    MainBrainAgent,
    SupervisorAgent,
    RouterAgent,
    ExecutorAgent,
    MemoryManagerAgent
)
from core_logic import (
    load_user_memory,
    parse_main_brain_json,
    format_main_brain_output,
    supervise_and_retry_main_brain,
    process_actions_loop
)


def main():
    """主函数"""
    print("=" * 60)
    print("MCP 工具集成 - 主脑任务分发系统")
    print("=" * 60)
    print("\n提示: 输入 'quit' 或 'exit' 退出程序")
    print("提示: 输入 'help' 查看帮助信息")
    print("提示: 输入 'tools' 查看可用工具列表")
    print("-" * 60)
    
    # 初始化 MCP 客户端管理器（从 mcp.json 读取配置）
    print("\n[初始化] 正在加载 MCP 客户端管理器...")
    mcp_client_manager = MCPClientManager()
    mcp_client_manager.initialize_all()
    print(f"  ✓ MCP 客户端管理器初始化完成")
    
    # 获取所有工具定义
    tools = mcp_client_manager.get_all_tools()
    print(f"  ✓ 已加载 {len(tools)} 个 MCP 工具")

    # 初始化所有 AI Agent（每个都有独立的实例和日志文件）
    print("\n[初始化] 正在启动 AI Agents...")
    
    # 读取用户记忆
    user_memory = load_user_memory()
    
    # 主脑 AI Agent
    main_brain_agent = MainBrainAgent(
        provider='deepseek',
        user_memory=user_memory
    )
    print("  ✓ 主脑AI Agent 初始化完成")
    
    # 监督 AI Agent
    supervisor_agent = SupervisorAgent(provider='deepseek')
    print("  ✓ 监督AI Agent 初始化完成")
    
    # 路由 AI Agent
    router_agent = RouterAgent(provider='deepseek')
    print("  ✓ 路由AI Agent 初始化完成")
    
    # 执行 AI Agent
    executor_agent = ExecutorAgent(provider='deepseek')
    print("  ✓ 执行AI Agent 初始化完成")
    
    # 记忆管理 AI Agent
    memory_manager_agent = MemoryManagerAgent(provider='deepseek')
    print("  ✓ 记忆管理AI Agent 初始化完成")
    
    print("\n" + "=" * 60)
    print("初始化完成！开始交互...")
    print("=" * 60 + "\n")
    
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
            
            if user_input.lower() == 'tools':
                print("\n可用 MCP 工具:")
                for i, tool in enumerate(tools, 1):
                    print(f"  {i}. {tool['name']}: {tool['description']}")
                continue
            
            if user_input.lower() == 'history':
                history = main_brain_agent.get_history()
                print(f"\n对话历史 ({len(history)} 条):")
                for i, msg in enumerate(history[-10:], 1):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:100]
                    print(f"  {i}. [{role}]: {content}...")
                continue
            
            if user_input.lower() == 'clear':
                main_brain_agent.clear_history()
                print("\n✓ 对话历史已清空")
                continue
            
            # 发送消息给主脑 AI
            conversation_count += 1
            
            # 获取当前时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_weekday = datetime.now().strftime("%A")
            
            # 在用户输入前添加时间信息
            user_input_with_time = f"[当前时间: {current_time} ({current_date} {current_weekday})]\n\n{user_input}"
            
            # 在每次调用主脑AI前，重新加载用户记忆并更新系统提示词
            user_memory = load_user_memory()
            main_brain_agent.update_user_memory(user_memory)
            
            # 调用主脑 AI
            response = main_brain_agent.chat(
                content=user_input_with_time,
                max_tokens=1500,
                temperature=0.7
            )
            
            if not response.get("success"):
                print(f"\n✗ 错误: {response.get('message', '未知错误')}")
                continue
            
            ai_response = response["content"]
            
            # 解析主脑输出的 ActionSpec JSON
            main_brain_json = parse_main_brain_json(ai_response)
            
            if not main_brain_json:
                print("\n✗ 错误: 无法解析主脑输出的 JSON 格式")
                continue
            
            # 验证顶层结构
            if "actions" not in main_brain_json:
                print("\n✗ 错误: ActionSpec JSON 格式错误，顶层必须包含 'actions' 字段")
                continue
            
            # 格式化并输出主脑AI的输出（文本格式，不显示原始JSON）
            formatted_output = format_main_brain_output(main_brain_json)
            print(f"\n🧠 [主脑AI] {formatted_output}")
            
            # 检查actions中是否包含mcp类型的action
            actions = main_brain_json.get("actions", [])
            has_mcp_action = any(action.get("type") == "mcp" for action in actions)
            
            # 只有包含mcp类型的action时才调用监督AI
            if has_mcp_action:
                # 监督主脑AI的输出
                main_brain_json, ai_response = supervise_and_retry_main_brain(
                    main_brain_agent=main_brain_agent,
                    supervisor_agent=supervisor_agent,
                    user_input=user_input,
                    main_brain_output=ai_response,
                    main_brain_json=main_brain_json,
                    max_retries=3
                )
                
                if not main_brain_json:
                    print("\n✗ 错误: 监督流程失败")
                    continue
                
                # 重新获取actions（监督后可能被修改）
                actions = main_brain_json.get("actions", [])
            
            if not actions:
                print("\n✗ 警告: actions 数组为空")
                continue
            
            # 处理actions（包括MCP执行和循环反馈）
            # 提取原始用户输入（移除时间信息）
            original_user_input = user_input
            if user_input_with_time.startswith('[当前时间:'):
                lines = user_input_with_time.split('\n', 2)
                if len(lines) > 2:
                    original_user_input = lines[2]
            
            process_actions_loop(
                main_brain_agent=main_brain_agent,
                router_agent=router_agent,
                executor_agent=executor_agent,
                memory_manager_agent=memory_manager_agent,
                mcp_client_manager=mcp_client_manager,
                actions=actions,
                max_iterations=10,
                current_user_input=original_user_input,
                current_ai_output=ai_response
            )
        
        except KeyboardInterrupt:
            print("\n\n程序被用户中断")
            break
        except Exception as e:
            print(f"\n✗ 发生错误: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

