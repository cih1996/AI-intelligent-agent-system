#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌面操作助手 MCP 服务器
基于 GPT-4o 和 JS 脚本执行引擎
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
import time
from dotenv import load_dotenv

# 导入核心模块
from core.gpt_client import GPTClient
from core.system_info import SystemInfo
from core.screenshot import ScreenshotManager
from core.js_executor import JSExecutor


class DesktopAssistantServer:
    """桌面操作助手服务器"""
    
    def __init__(self, data_dir: Path = None):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录
        """
        # 加载 .env 文件
        self._load_env()
        
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # 默认数据目录
            plugin_dir = Path(__file__).parent
            project_root = plugin_dir.parent.parent
            self.data_dir = project_root / '.mcp_data' / 'desktop_assistant'
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 临时文件目录
        self.temp_dir = self.data_dir / 'temp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志目录
        self.log_dir = self.data_dir / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.screenshot_manager = ScreenshotManager(self.temp_dir)
        self.system_info = SystemInfo()
        
        # 通信目录（用于Python和JS之间的文件通信）
        comm_dir = self.data_dir / 'comm'
        comm_dir.mkdir(parents=True, exist_ok=True)
        
        self.js_executor = JSExecutor(
            screenshot_manager=self.screenshot_manager,
            system_info=self.system_info,
            comm_dir=comm_dir
        )
        
        # GPT客户端（从 .env 文件读取配置）
        self.gpt_client = None
        self._init_gpt_client()
        
        # 加载系统提示词
        self.system_prompt = self._load_system_prompt()
        
        print(f"[DesktopAssistant] 服务器初始化完成")
        print(f"[DesktopAssistant] 数据目录: {self.data_dir}")
        print(f"[DesktopAssistant] 临时目录: {self.temp_dir}")
    
    def _load_env(self):
        """加载 .env 文件"""
        # 查找 .env 文件（优先使用当前目录下的）
        plugin_dir = Path(__file__).parent
        env_path = plugin_dir / '.env'
        
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[DesktopAssistant] 已加载 .env 文件: {env_path}")
        else:
            # 如果当前目录没有，尝试项目根目录
            project_root = plugin_dir.parent.parent
            env_path = project_root / '.env'
            if env_path.exists():
                load_dotenv(env_path)
                print(f"[DesktopAssistant] 已加载 .env 文件: {env_path}")
            else:
                print(f"[DesktopAssistant] 警告: 未找到 .env 文件，将使用系统环境变量")
                print(f"[DesktopAssistant] 提示: 请在 {plugin_dir / '.env'} 创建配置文件")
                # 尝试从系统环境变量加载（不覆盖）
                load_dotenv(override=False)
    
    def _init_gpt_client(self):
        """初始化GPT客户端（从 .env 文件读取配置）"""
        # 从环境变量读取配置（已通过 load_dotenv 加载到环境变量中）
        api_key = os.environ.get('OPENAI_API_KEY')
        base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        model = os.environ.get('DESKTOP_ASSISTANT_MODEL', 'gpt-4o')
        use_proxy = os.environ.get('USE_PROXY', 'false').lower() == 'true'
        proxy_url = os.environ.get('PROXY_URL')
        
        if not api_key or api_key == 'your_openai_api_key_here':
            print("[DesktopAssistant] 警告: OPENAI_API_KEY 未设置或为默认值，GPT功能将不可用")
            print("[DesktopAssistant] 请在 .env 文件中设置正确的 OPENAI_API_KEY")
            return
        
        try:
            self.gpt_client = GPTClient(
                api_key=api_key,
                base_url=base_url,
                model=model,
                use_proxy=use_proxy,
                proxy_url=proxy_url,
                log_dir=self.log_dir  # 传递日志目录
            )
            print(f"[DesktopAssistant] GPT客户端初始化成功，模型: {model}")
            print(f"[DesktopAssistant] 对话日志将保存到: {self.log_dir}")
        except Exception as e:
            print(f"[DesktopAssistant] GPT客户端初始化失败: {str(e)}")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        prompt_path = Path(__file__).parent / 'prompts' / 'system_prompt.txt'
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[DesktopAssistant] 加载系统提示词失败: {str(e)}")
            return "你是一个专业的桌面操作助手。"
    
    def _is_javascript_code(self, text: str) -> bool:
        """
        判断文本是否是JavaScript代码（通过格式标记识别）
        
        Args:
            text: 待判断的文本
            
        Returns:
            如果是JS代码返回True，否则返回False
        """
        if not text or not text.strip():
            return False
        
        text = text.strip()
        
        # 检查格式标记
        has_js_marker = "[JS_CODE]" in text or "[/JS_CODE]" in text
        has_complete_marker = "[COMPLETE]" in text or "[/COMPLETE]" in text
        
        if has_js_marker:
            print(f"[识别] 检测到 [JS_CODE] 标记，判断为JS代码")
            return True
        
        if has_complete_marker:
            print(f"[识别] 检测到 [COMPLETE] 标记，判断为完成报告")
            return False
        
        # 如果没有标记，尝试兼容旧格式（向后兼容）
        # 检查markdown代码块
        if text.startswith("```javascript") or text.startswith("```js") or "```javascript" in text:
            print(f"[识别] 检测到markdown代码块，判断为JS代码（兼容模式）")
            return True
        
        # 检查完成报告关键词（仅在开头）
        if text.startswith("任务完成报告：") or text.startswith("任务状态："):
            print(f"[识别] 检测到完成报告格式，判断为完成报告（兼容模式）")
            return False
        
        # 默认：如果没有明确标记，尝试检测JS代码特征（向后兼容）
        js_keywords = ["function", "async", "await", "const", "let", "log(", "mouseClick", "keyboardType"]
        has_js_keywords = any(keyword in text for keyword in js_keywords)
        
        if has_js_keywords:
            print(f"[识别] 未检测到格式标记，但包含JS关键词，判断为JS代码（兼容模式）")
            return True
        
        print(f"[识别] 未检测到格式标记和JS特征，判断为完成报告（兼容模式）")
        return False
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "desktop_assistant.chat":
            return self._chat(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _chat(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        桌面操作助手主方法
        
        Args:
            arguments: 包含 instruction 参数
            
        Returns:
            执行结果
        """
        instruction = arguments.get("instruction", "")
        if not instruction:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: instruction"
            }
        
        print(f"[DesktopAssistant] 收到指令: {instruction}")
        
        try:
            # 1. 获取系统信息
            print("[DesktopAssistant] 步骤1: 获取系统信息...")
            open_windows = self.system_info.get_open_windows()
            
            # 2. 截取当前屏幕
            print("[DesktopAssistant] 步骤2: 截取当前屏幕...")
            screenshot_path = self.screenshot_manager.capture_screen(scale_factor=0.5)
            
            # 3. 构建提示词
            print("[DesktopAssistant] 步骤3: 构建提示词...")
            context_info = f"""
当前系统状态：
- 已打开窗口数量: {len(open_windows)}

已打开窗口列表:
{json.dumps([{'title': w['title'], 'x': w['x'], 'y': w['y'], 'width': w['width'], 'height': w['height']} for w in open_windows[:10]], ensure_ascii=False, indent=2)}

用户指令: {instruction}

请根据以上信息生成JavaScript代码来执行用户指令。
"""
            
            # 4. 调用GPT生成JS代码
            print("[DesktopAssistant] 步骤4: 调用GPT生成JS代码...")
            if not self.gpt_client:
                return {
                    "success": False,
                    "content": None,
                    "error": "GPT客户端未初始化，请设置OPENAI_API_KEY环境变量"
                }
            
            gpt_result = self.gpt_client.chat_with_image(
                image_path=str(screenshot_path),
                text_prompt=context_info,
                system_prompt=self.system_prompt,
                max_tokens=4000,
                temperature=0.7
            )
            
            if not gpt_result.get("success"):
                return {
                    "success": False,
                    "content": None,
                    "error": f"GPT调用失败: {gpt_result.get('message', '未知错误')}"
                }
            
            gpt_output = gpt_result.get("content", "")
            print(f"[DesktopAssistant] GPT输出长度: {len(gpt_output)} 字符")
            print(f"[DesktopAssistant] GPT输出预览: {gpt_output[:200]}...")
            
            # 5. 判断输出格式
            is_js_code = self._is_javascript_code(gpt_output)
            print(f"[DesktopAssistant] 格式识别结果: {'JS代码' if is_js_code else '完成报告'}")
            
            if not is_js_code:
                # 输出的是完成报告，任务结束
                print("[DesktopAssistant] GPT输出完成报告，任务结束")
                completion_report = self._extract_completion_report(gpt_output)
                return {
                    "success": True,
                    "content": {
                        "message": completion_report,
                        "type": "completion_report"
                    },
                    "error": None
                }
            
            # 提取JS代码（移除markdown标记）
            js_code = self._extract_javascript_code(gpt_output)
            print(f"[DesktopAssistant] 识别为JS代码，长度: {len(js_code)} 字符")
            
            # 6. 执行JS代码
            print("[DesktopAssistant] 步骤6: 执行JS代码...")
            execution_result = self.js_executor.execute_js(js_code)
            
            if not execution_result.get("success"):
                # 执行失败，将错误信息反馈给GPT
                print("[DesktopAssistant] JS执行失败，反馈给GPT...")
                return self._continue_with_feedback(instruction, execution_result, None)
            
            # 7. 智能截图检查变化
            print("[DesktopAssistant] 步骤7: 检查屏幕变化...")
            change_screenshot = self.screenshot_manager.capture_changes()
            
            # 8. 将执行结果反馈给GPT，让GPT决定是否继续
            print("[DesktopAssistant] 将执行结果反馈给GPT...")
            return self._continue_with_feedback(instruction, execution_result, change_screenshot)
                
        except Exception as e:
            print(f"[DesktopAssistant] 执行失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "content": None,
                "error": f"执行失败: {str(e)}"
            }
    
    def _retry_with_screenshot(self, instruction: str, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """执行失败后，截图并重新生成代码（已废弃，使用 _continue_with_feedback）"""
        # 直接使用反馈机制
        return self._continue_with_feedback(instruction, execution_result, None)
    
    def _extract_javascript_code(self, text: str) -> str:
        """
        从文本中提取JavaScript代码（根据格式标记提取）
        
        Args:
            text: 包含JS代码的文本
            
        Returns:
            提取的JS代码
        """
        text = text.strip()
        
        # 优先使用格式标记提取
        if "[JS_CODE]" in text:
            # 提取 [JS_CODE] 和 [/JS_CODE] 之间的内容
            start_marker = "[JS_CODE]"
            end_marker = "[/JS_CODE]"
            
            start_idx = text.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = text.find(end_marker, start_idx)
                if end_idx != -1:
                    code = text[start_idx:end_idx].strip()
                    print(f"[提取] 从格式标记中提取JS代码，长度: {len(code)} 字符")
                    return code
        
        # 兼容旧格式：markdown代码块
        if text.startswith("```javascript"):
            text = text.replace("```javascript", "", 1).strip()
        elif text.startswith("```js"):
            text = text.replace("```js", "", 1).strip()
        elif text.startswith("```"):
            parts = text.split("```", 2)
            if len(parts) >= 3:
                text = parts[1].strip()
            else:
                text = parts[-1].strip()
        
        # 移除末尾的 ```
        if text.endswith("```"):
            text = text[:-3].strip()
        
        print(f"[提取] 从markdown代码块中提取JS代码（兼容模式），长度: {len(text)} 字符")
        return text
    
    def _extract_completion_report(self, text: str) -> str:
        """
        从文本中提取完成报告
        
        Args:
            text: 包含完成报告的文本
            
        Returns:
            提取的完成报告
        """
        text = text.strip()
        
        # 使用格式标记提取
        if "[COMPLETE]" in text:
            start_marker = "[COMPLETE]"
            end_marker = "[/COMPLETE]"
            
            start_idx = text.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = text.find(end_marker, start_idx)
                if end_idx != -1:
                    report = text[start_idx:end_idx].strip()
                    print(f"[提取] 从格式标记中提取完成报告")
                    return report
        
        # 兼容旧格式：直接返回
        return text
    
    def _continue_with_feedback(self, instruction: str, execution_result: Dict[str, Any], screenshot_path: Path = None) -> Dict[str, Any]:
        """
        将执行结果反馈给GPT，让GPT决定是否继续
        
        Args:
            instruction: 用户原始指令
            execution_result: JS执行结果
            screenshot_path: 截图路径（如果有）
            
        Returns:
            执行结果
        """
        try:
            # 构建反馈信息
            feedback_prompt = f"""
用户指令: {instruction}

上次执行结果:
- 执行状态: {'成功' if execution_result.get('success') else '失败'}
- 执行日志:
{json.dumps(execution_result.get('log', []), ensure_ascii=False, indent=2)}
"""
            
            if not execution_result.get('success'):
                feedback_prompt += f"\n错误信息: {execution_result.get('error', '未知错误')}"
            
            feedback_prompt += "\n\n请根据执行结果判断："
            feedback_prompt += "\n1. 如果任务未完成，需要继续执行 → 输出JavaScript代码"
            feedback_prompt += "\n2. 如果任务已完成 → 输出完成报告（格式：任务完成报告：\\n任务状态：完成\\n执行结果：...）"
            feedback_prompt += "\n3. 如果遇到错误无法继续 → 输出失败报告（格式：任务完成报告：\\n任务状态：失败\\n原因：...）"
            
            # 如果有截图，发送截图
            if screenshot_path and screenshot_path.exists():
                gpt_result = self.gpt_client.chat_with_image(
                    image_path=str(screenshot_path),
                    text_prompt=feedback_prompt,
                    system_prompt=self.system_prompt,
                    max_tokens=4000,
                    temperature=0.7
                )
            else:
                # 没有截图，只发送文本
                gpt_result = self.gpt_client.chat(
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": feedback_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.7
                )
            
            if not gpt_result.get("success"):
                return {
                    "success": False,
                    "content": None,
                    "error": f"GPT反馈失败: {gpt_result.get('message', '未知错误')}"
                }
            
            gpt_output = gpt_result.get("content", "")
            
            # 判断输出格式
            is_js_code = self._is_javascript_code(gpt_output)
            
            if not is_js_code:
                # 输出的是完成报告，任务结束
                print("[DesktopAssistant] GPT输出完成报告，任务结束")
                completion_report = self._extract_completion_report(gpt_output)
                return {
                    "success": True,
                    "content": {
                        "message": completion_report,
                        "type": "completion_report",
                        "execution_log": execution_result.get("log", []),
                        "final_screenshot": str(screenshot_path) if screenshot_path else None
                    },
                    "error": None
                }
            
            # 继续执行JS代码
            print("[DesktopAssistant] GPT输出JS代码，继续执行...")
            js_code = self._extract_javascript_code(gpt_output)
            execution_result = self.js_executor.execute_js(js_code)
            
            if not execution_result.get("success"):
                # 执行失败，再次反馈
                print("[DesktopAssistant] JS执行失败，再次反馈给GPT...")
                return self._continue_with_feedback(instruction, execution_result, None)
            
            # 检查屏幕变化并继续反馈
            change_screenshot = self.screenshot_manager.capture_changes()
            return self._continue_with_feedback(instruction, execution_result, change_screenshot)
            
        except Exception as e:
            print(f"[DesktopAssistant] 反馈处理失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "content": None,
                "error": f"反馈处理失败: {str(e)}"
            }
    
    def _check_if_continue(self, instruction: str, screenshot_path: Path, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """检查是否需要继续执行"""
        try:
            prompt = f"""
用户指令: {instruction}

执行日志:
{json.dumps(execution_result.get('log', []), ensure_ascii=False, indent=2)}

当前屏幕截图已更新。请判断：
1. 任务是否已完成？
2. 如果未完成，是否需要继续执行下一步操作？

请以JSON格式回复：
{{
    "should_continue": true/false,
    "message": "说明信息",
    "reason": "判断理由"
}}
"""
            
            gpt_result = self.gpt_client.chat_with_image(
                image_path=str(screenshot_path),
                text_prompt=prompt,
                system_prompt="你是一个任务状态判断助手。请根据截图和执行日志判断任务是否完成。",
                max_tokens=500,
                temperature=0.3
            )
            
            if not gpt_result.get("success"):
                return {
                    "should_continue": False,
                    "message": "无法判断，默认结束",
                    "reason": "GPT调用失败"
                }
            
            # 解析JSON响应
            content = gpt_result.get("content", "")
            try:
                # 尝试提取JSON
                import re
                json_match = re.search(r'\{[^{}]*"should_continue"[^{}]*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    # 如果没有找到JSON，尝试直接解析
                    result = json.loads(content)
                    return result
            except:
                # 解析失败，默认继续
                return {
                    "should_continue": True,
                    "message": "无法解析GPT响应，默认继续",
                    "reason": "JSON解析失败"
                }
                
        except Exception as e:
            print(f"[DesktopAssistant] 判断是否继续失败: {str(e)}")
            return {
                "should_continue": False,
                "message": "判断失败，默认结束",
                "reason": str(e)
            }


def create_server(data_dir: str = None) -> DesktopAssistantServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        DesktopAssistantServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'desktop_assistant'
    
    return DesktopAssistantServer(data_path)


def main():
    """主函数，用于单独测试"""
    import sys
    
    print("=" * 60)
    print("Desktop Assistant MCP Server - 测试模式")
    print("=" * 60)
    
    # 检查 .env 文件
    plugin_dir = Path(__file__).parent
    env_path = plugin_dir / '.env'
    
    if not env_path.exists():
        print(f"\n[警告] 未找到 .env 文件: {env_path}")
        print("请创建 .env 文件并配置以下内容:")
        print("\n  OPENAI_API_KEY=your_api_key")
        print("  OPENAI_BASE_URL=https://api.openai.com/v1")
        print("  DESKTOP_ASSISTANT_MODEL=gpt-4o")
        print("  USE_PROXY=false")
        print("  PROXY_URL=http://127.0.0.1:7890")
        print(f"\n.env 文件路径: {env_path}")
        sys.exit(1)
    
    # 检查 API Key
    load_dotenv(env_path)
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key or api_key == 'your_openai_api_key_here':
        print("\n[警告] OPENAI_API_KEY 未设置或为默认值")
        print(f"请在 .env 文件中设置正确的 OPENAI_API_KEY")
        print(f".env 文件路径: {env_path}")
        sys.exit(1)
    
    # 创建服务器实例
    print("\n[1/3] 初始化服务器...")
    server = create_server()
    
    if not server.gpt_client:
        print("\n[错误] GPT客户端初始化失败")
        sys.exit(1)
    
    print("[✓] 服务器初始化成功")
    
    # 测试系统信息获取
    print("\n[2/3] 测试系统信息获取...")
    try:
        windows = server.system_info.get_open_windows()
        print(f"[✓] 获取到 {len(windows)} 个打开窗口")
    except Exception as e:
        print(f"[✗] 系统信息获取失败: {str(e)}")
    
    # 测试截图
    print("\n[3/3] 测试截图功能...")
    try:
        screenshot_path = server.screenshot_manager.capture_screen(scale_factor=0.5)
        print(f"[✓] 截图成功: {screenshot_path}")
        print(f"[✓] 文件大小: {screenshot_path.stat().st_size} bytes")
    except Exception as e:
        print(f"[✗] 截图失败: {str(e)}")
    
    # 交互式测试
    print("\n" + "=" * 60)
    print("进入交互式测试模式")
    print("输入指令进行测试（输入 'quit' 或 'exit' 退出）")
    print("=" * 60)
    
    while True:
        try:
            instruction = input("\n请输入指令: ").strip()
            
            if not instruction:
                continue
            
            if instruction.lower() in ['quit', 'exit', 'q']:
                print("\n退出测试模式")
                break
            
            print(f"\n[执行] {instruction}")
            print("-" * 60)
            
            # 调用工具
            result = server.call_tool("desktop_assistant.chat", {
                "instruction": instruction
            })
            
            # 显示结果
            print("\n[结果]")
            if result.get("success"):
                content = result.get("content", {})
                print(f"  状态: 成功")
                print(f"  消息: {content.get('message', '无')}")
                
                log = content.get("execution_log", [])
                if log:
                    print(f"\n  执行日志 ({len(log)} 条):")
                    for i, entry in enumerate(log[:10], 1):  # 只显示前10条
                        msg = entry.get("message", "")
                        print(f"    {i}. {msg}")
                    if len(log) > 10:
                        print(f"    ... 还有 {len(log) - 10} 条日志")
            else:
                error = result.get("error", "未知错误")
                print(f"  状态: 失败")
                print(f"  错误: {error}")
            
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n用户中断，退出测试模式")
            break
        except Exception as e:
            print(f"\n[错误] 执行失败: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

