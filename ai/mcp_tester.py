#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具交互式测试器
用于测试单个 MCP 插件的工具，支持参数输入和结果展示
"""

import json
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from utils.mcp_client import MCPClientManager


class MCPTester:
    """MCP 工具测试器（通过 HTTP 调用）"""
    
    def __init__(self):
        """初始化测试器"""
        self.client_manager = MCPClientManager()
        self.current_server = None
        self.current_server_tools = []
    
    def print_header(self, text: str):
        """打印标题"""
        print("\n" + "=" * 60)
        print(f"  {text}")
        print("=" * 60)
    
    def print_success(self, text: str):
        """打印成功消息"""
        print(f"\n✓ {text}")
    
    def print_error(self, text: str):
        """打印错误消息"""
        print(f"\n✗ {text}", file=sys.stderr)
    
    def print_info(self, text: str):
        """打印信息消息"""
        print(f"\nℹ {text}")
    
    def list_servers(self) -> List[str]:
        """列出所有可用的 MCP 服务器"""
        self.print_header("MCP 服务器列表")
        
        if not self.client_manager.clients:
            self.print_error("未找到任何 MCP 服务器配置")
            self.print_info("请确保 mcp.json 配置文件存在且包含服务器配置")
            return []
        
        server_names = list(self.client_manager.clients.keys())
        
        print(f"\n发现 {len(server_names)} 个 MCP 服务器：")
        for i, name in enumerate(server_names, 1):
            config = self.client_manager.server_configs.get(name, {})
            url = config.get('url', '未知')
            print(f"  {i}. {name} ({url})")
        
        return server_names
    
    def select_server(self, server_name: str) -> bool:
        """选择指定服务器并获取其工具列表"""
        try:
            if server_name not in self.client_manager.clients:
                self.print_error(f"服务器 '{server_name}' 不存在")
                return False
            
            self.print_info(f"正在连接服务器: {server_name}")
            
            # 获取该服务器的所有工具
            all_tools = self.client_manager.get_all_tools()
            server_tools = [tool for tool in all_tools if tool.get('server') == server_name]
            
            if not server_tools:
                self.print_error(f"服务器 '{server_name}' 没有可用工具")
                return False
            
            self.current_server = server_name
            self.current_server_tools = server_tools
            self.print_success(f"服务器 {server_name} 连接成功，找到 {len(server_tools)} 个工具")
            return True
        except Exception as e:
            self.print_error(f"连接服务器失败: {str(e)}")
            return False
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出当前服务器的所有工具"""
        return self.current_server_tools
    
    def display_tool_info(self, tool: Dict[str, Any]):
        """显示工具的详细信息"""
        tool_name = tool.get('name', '未知')
        description = tool.get('description', '无描述')
        # 支持两种命名方式：inputSchema (MCP标准) 和 input_schema (本地格式)
        input_schema = tool.get('inputSchema', tool.get('input_schema', {}))
        properties = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        print(f"\n工具名称: {tool_name}")
        print(f"描述: {description}")
        
        if properties:
            print("\n参数列表:")
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '无描述')
                is_required = param_name in required
                required_mark = "【必需】" if is_required else "【可选】"
                
                # 处理枚举类型
                if 'enum' in param_info:
                    enum_values = param_info['enum']
                    print(f"  {param_name} ({param_type}) {required_mark}")
                    print(f"    描述: {param_desc}")
                    print(f"    可选值: {', '.join(map(str, enum_values))}")
                # 处理数组类型
                elif param_type == 'array':
                    items = param_info.get('items', {})
                    items_type = items.get('type', 'string')
                    print(f"  {param_name} (array<{items_type}>) {required_mark}")
                    print(f"    描述: {param_desc}")
                # 处理对象类型
                elif param_type == 'object':
                    print(f"  {param_name} (object) {required_mark}")
                    print(f"    描述: {param_desc}")
                else:
                    default = param_info.get('default', '')
                    default_str = f" (默认: {default})" if default else ""
                    print(f"  {param_name} ({param_type}) {required_mark}{default_str}")
                    print(f"    描述: {param_desc}")
 
    
    def input_parameter(self, param_name: str, param_info: Dict[str, Any], required: bool) -> Any:
        """输入单个参数"""
        param_type = param_info.get('type', 'string')
        param_desc = param_info.get('description', '')
        default = param_info.get('default', '')
        
        # 构建提示文本
        prompt = f"请输入 {param_name}"
        if param_desc:
            prompt += f" ({param_desc})"
        if default:
            prompt += f" [默认: {default}]"
        if not required:
            prompt += " [可选，直接回车跳过]"
        prompt += ": "
        
        while True:
            try:
                value = input(prompt).strip()
                
                # 处理空值
                if not value:
                    if required and not default:
                        print("  该参数为必需参数，不能为空")
                        continue
                    elif default:
                        return default
                    else:
                        return None
                
                # 根据类型转换值
                if param_type == 'integer':
                    return int(value)
                elif param_type == 'number':
                    return float(value)
                elif param_type == 'boolean':
                    return value.lower() in ('true', '1', 'yes', 'y', '是')
                elif param_type == 'array':
                    # 支持逗号分隔或JSON格式
                    if value.startswith('['):
                        return json.loads(value)
                    else:
                        return [item.strip() for item in value.split(',') if item.strip()]
                elif param_type == 'object':
                    return json.loads(value)
                elif 'enum' in param_info:
                    enum_values = param_info['enum']
                    if value not in enum_values:
                        print(f"  无效值，必须是以下之一: {', '.join(map(str, enum_values))}")
                        continue
                    return value
                else:
                    return value
                    
            except ValueError as e:
                print(f"  输入格式错误: {str(e)}，请重试")
            except json.JSONDecodeError as e:
                print(f"  JSON 格式错误: {str(e)}，请重试")
    
    def collect_arguments(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        """收集工具参数"""
        # 支持两种命名方式：inputSchema (MCP标准) 和 input_schema (本地格式)
        input_schema = tool.get('inputSchema', tool.get('input_schema', {}))
        properties = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        arguments = {}
        
        if not properties:
            return arguments
        
        print("\n" + "-" * 60)
        print("请输入参数值:")
        print("-" * 60)
        
        for param_name, param_info in properties.items():
            is_required = param_name in required
            value = self.input_parameter(param_name, param_info, is_required)
            
            if value is not None:
                arguments[param_name] = value
        
        return arguments
    
    def test_tool(self, tool: Dict[str, Any], arguments: Dict[str, Any]) -> Dict[str, Any]:
        """测试工具"""
        tool_name = tool.get('name')
        
        self.print_info(f"正在执行工具: {tool_name}")
        print(f"参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
        
        try:
            result = self.client_manager.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"执行异常: {str(e)}"
            }
    
    def display_result(self, result: Dict[str, Any]):
        """显示执行结果"""
        print("\n" + "=" * 60)
        print("执行结果:")
        print("=" * 60)
        
        success = result.get('success', False)
        if success:
            self.print_success("工具执行成功")
        else:
            self.print_error("工具执行失败")
        
        content = result.get('content')
        error = result.get('error')
        
        if error:
            print(f"\n错误信息: {error}")
        
        if content is not None:
            print("\n返回内容:")
            if isinstance(content, (dict, list)):
                print(json.dumps(content, ensure_ascii=False, indent=2))
            else:
                print(content)
    
    def run(self):
        """运行测试器主循环"""
        print("\n" + "=" * 60)
        print("  MCP 工具交互式测试器 (HTTP 模式)")
        print("=" * 60)
        
        # 初始化 MCP 客户端管理器
        self.print_info("正在初始化 MCP 客户端管理器...")
        self.client_manager.initialize_all()
        
        if not self.client_manager.clients:
            self.print_error("没有可用的 MCP 服务器")
            self.print_info("请确保：")
            self.print_info("1. mcp.json 配置文件存在且格式正确")
            self.print_info("2. MCP 服务器已启动（运行: python start_mcp_server.py --host 0.0.0.0 --base-port 8000）")
            return
        
        # 列出服务器
        server_names = self.list_servers()
        if not server_names:
            return
        
        # 选择服务器
        while True:
            try:
                choice = input(f"\n请选择要测试的服务器 (1-{len(server_names)}, 输入 q 退出): ").strip()
                
                if choice.lower() == 'q':
                    print("\n再见！")
                    return
                
                server_index = int(choice) - 1
                if 0 <= server_index < len(server_names):
                    server_name = server_names[server_index]
                    if self.select_server(server_name):
                        break
                else:
                    print(f"无效选择，请输入 1-{len(server_names)} 之间的数字")
            except ValueError:
                print("请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n再见！")
                return
        
        # 工具测试循环
        while True:
            try:
                # 列出工具
                tools = self.list_tools()
                if not tools:
                    self.print_error("该插件没有可用工具")
                    break
                
                self.print_header(f"服务器 {self.current_server} 的工具列表")
                for i, tool in enumerate(tools, 1):
                    tool_name = tool.get('name', '未知')
                    tool_desc = tool.get('description', '无描述')
                    print(f"  {i}. {tool_name}")
                    print(f"     {tool_desc}")
                
                # 选择工具
                tool_choice = input(f"\n请选择要测试的工具 (1-{len(tools)}, 输入 b 返回服务器列表, q 退出): ").strip()
                
                if tool_choice.lower() == 'q':
                    print("\n再见！")
                    break
                
                if tool_choice.lower() == 'b':
                    # 重新选择服务器
                    server_names = self.list_servers()
                    if not server_names:
                        break
                    continue
                
                tool_index = int(tool_choice) - 1
                if not (0 <= tool_index < len(tools)):
                    print(f"无效选择，请输入 1-{len(tools)} 之间的数字")
                    continue
                
                selected_tool = tools[tool_index]
                
                # 显示工具信息
                self.print_header(f"工具: {selected_tool.get('name')}")
                self.display_tool_info(selected_tool)
                
                # 收集参数
                print(selected_tool)
                arguments = self.collect_arguments(selected_tool)
                
                # 确认执行
                confirm = input("\n确认执行? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("已取消")
                    continue
                
                # 执行工具
                result = self.test_tool(selected_tool, arguments)
                
                # 显示结果
                self.display_result(result)
                
                # 询问是否继续
                continue_choice = input("\n继续测试? (y/n): ").strip().lower()
                if continue_choice != 'y':
                    break
                    
            except ValueError:
                print("请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                self.print_error(f"发生错误: {str(e)}")
                import traceback
                traceback.print_exc()


def main():
    """主函数"""
    tester = MCPTester()
    tester.run()


if __name__ == '__main__':
    main()

