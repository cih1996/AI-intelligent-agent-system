#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Windows系统操作 MCP 服务器
符合 MCP 协议标准
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import sys

try:
    import win32gui
    import win32con
    import win32api
    WIN32_AVAILABLE = True
except ImportError as e:
    WIN32_AVAILABLE = False
    print(f"[SystemTool] 警告: pywin32 导入失败，窗口操作功能将不可用")
    print(f"[SystemTool] 错误详情: {str(e)}")
    print(f"[SystemTool] 提示: 如果已安装 pywin32，请运行: python -m pywin32_postinstall -install")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[SystemTool] 警告: pyautogui 未安装，鼠标和键盘操作功能将不可用")

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("[SystemTool] 警告: PaddleOCR 未安装，OCR功能将不可用")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[SystemTool] 警告: Pillow 未安装，OCR功能将不可用")


class SystemServer:
    """Windows系统操作服务器"""
    
    def __init__(self, config_dir: Path):
        """
        初始化服务器
        
        Args:
            config_dir: 配置存储目录
        """
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化OCR（延迟加载）
        self._ocr = None
        
        # 窗口句柄缓存
        self._window_cache = {}
    
    def _get_ocr(self):
        """获取OCR实例（延迟初始化）"""
        if not PADDLEOCR_AVAILABLE:
            return None
        
        if self._ocr is None:
            try:
                self._ocr = PaddleOCR(use_angle_cls=True, lang='ch')
            except Exception as e:
                print(f"[SystemTool] OCR初始化失败: {e}")
                return None
        
        return self._ocr
    
    def _find_window_by_title(self, window_title: str) -> Optional[int]:
        """
        根据窗口标题查找窗口句柄
        
        Args:
            window_title: 窗口标题（支持部分匹配）
            
        Returns:
            窗口句柄，如果未找到返回None
        """
        if not WIN32_AVAILABLE:
            return None
        
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and window_title.lower() in title.lower():
                    windows.append((hwnd, title))
            return True
        
        windows = []
        try:
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            if windows:
                # 返回第一个匹配的窗口句柄
                return windows[0][0]
        except Exception as e:
            print(f"[SystemTool] 查找窗口失败: {e}")
        
        return None
    
    def _get_window_handle(self, window_title: Optional[str] = None, hwnd: Optional[int] = None) -> Optional[int]:
        """
        获取窗口句柄
        
        Args:
            window_title: 窗口标题
            hwnd: 窗口句柄
            
        Returns:
            窗口句柄
        """
        if hwnd:
            # 验证句柄是否有效
            if WIN32_AVAILABLE and win32gui.IsWindow(hwnd):
                return hwnd
        
        if window_title:
            return self._find_window_by_title(window_title)
        
        return None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name == "system.get_windows":
            return self._get_windows(arguments)
        elif tool_name == "system.window_close":
            return self._window_close(arguments)
        elif tool_name == "system.window_move":
            return self._window_move(arguments)
        elif tool_name == "system.window_hide":
            return self._window_hide(arguments)
        elif tool_name == "system.window_show":
            return self._window_show(arguments)
        elif tool_name == "system.window_minimize":
            return self._window_minimize(arguments)
        elif tool_name == "system.mouse_click":
            return self._mouse_click(arguments)
        elif tool_name == "system.keyboard_type":
            return self._keyboard_type(arguments)
        elif tool_name == "system.keyboard_press":
            return self._keyboard_press(arguments)
        elif tool_name == "system.ocr":
            return self._ocr_recognize(arguments)
        elif tool_name == "system.shell_execute":
            return self._shell_execute(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _get_windows(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """获取当前所有窗口列表"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pywin32 未安装，无法获取窗口列表"
            }
        
        include_minimized = arguments.get("include_minimized", True)
        windows = []
        
        def enum_windows_callback(hwnd, windows_list):
            if win32gui.IsWindow(hwnd):
                # 检查窗口是否可见
                if not include_minimized and not win32gui.IsWindowVisible(hwnd):
                    return True
                
                title = win32gui.GetWindowText(hwnd)
                if title:  # 只返回有标题的窗口
                    try:
                        # 获取窗口位置和大小
                        rect = win32gui.GetWindowRect(hwnd)
                        x, y, right, bottom = rect
                        width = right - x
                        height = bottom - y
                        
                        # 检查窗口状态
                        placement = win32gui.GetWindowPlacement(hwnd)
                        is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
                        is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                        
                        windows_list.append({
                            "hwnd": hwnd,
                            "title": title,
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                            "is_minimized": is_minimized,
                            "is_maximized": is_maximized,
                            "is_visible": win32gui.IsWindowVisible(hwnd)
                        })
                    except Exception as e:
                        print(f"[SystemTool] 获取窗口信息失败 {hwnd}: {e}")
            
            return True
        
        try:
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            return {
                "success": True,
                "content": {
                    "windows": windows,
                    "count": len(windows)
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"获取窗口列表失败: {str(e)}"
            }
    
    def _window_close(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """关闭指定窗口"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pywin32 未安装，无法关闭窗口"
            }
        
        window_title = arguments.get("window_title")
        hwnd = arguments.get("hwnd")
        
        handle = self._get_window_handle(window_title, hwnd)
        if not handle:
            return {
                "success": False,
                "content": None,
                "error": f"未找到窗口: {window_title or hwnd}"
            }
        
        try:
            win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
            return {
                "success": True,
                "content": {
                    "message": "窗口关闭命令已发送",
                    "hwnd": handle
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"关闭窗口失败: {str(e)}"
            }
    
    def _window_move(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """移动指定窗口"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pywin32 未安装，无法移动窗口"
            }
        
        window_title = arguments.get("window_title")
        hwnd = arguments.get("hwnd")
        x = arguments.get("x")
        y = arguments.get("y")
        
        if x is None or y is None:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: x, y"
            }
        
        handle = self._get_window_handle(window_title, hwnd)
        if not handle:
            return {
                "success": False,
                "content": None,
                "error": f"未找到窗口: {window_title or hwnd}"
            }
        
        try:
            # 获取当前窗口大小
            rect = win32gui.GetWindowRect(handle)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            # 移动窗口
            win32gui.SetWindowPos(handle, win32con.HWND_TOP, x, y, width, height, 
                                 win32con.SWP_SHOWWINDOW)
            
            return {
                "success": True,
                "content": {
                    "message": "窗口已移动",
                    "hwnd": handle,
                    "x": x,
                    "y": y
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"移动窗口失败: {str(e)}"
            }
    
    def _window_hide(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """隐藏指定窗口"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pywin32 未安装，无法隐藏窗口"
            }
        
        window_title = arguments.get("window_title")
        hwnd = arguments.get("hwnd")
        
        handle = self._get_window_handle(window_title, hwnd)
        if not handle:
            return {
                "success": False,
                "content": None,
                "error": f"未找到窗口: {window_title or hwnd}"
            }
        
        try:
            win32gui.ShowWindow(handle, win32con.SW_HIDE)
            return {
                "success": True,
                "content": {
                    "message": "窗口已隐藏",
                    "hwnd": handle
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"隐藏窗口失败: {str(e)}"
            }
    
    def _window_show(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """显示指定窗口"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pywin32 未安装，无法显示窗口"
            }
        
        window_title = arguments.get("window_title")
        hwnd = arguments.get("hwnd")
        
        handle = self._get_window_handle(window_title, hwnd)
        if not handle:
            return {
                "success": False,
                "content": None,
                "error": f"未找到窗口: {window_title or hwnd}"
            }
        
        try:
            win32gui.ShowWindow(handle, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(handle)
            return {
                "success": True,
                "content": {
                    "message": "窗口已显示",
                    "hwnd": handle
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"显示窗口失败: {str(e)}"
            }
    
    def _window_minimize(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """最小化指定窗口"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pywin32 未安装，无法最小化窗口"
            }
        
        window_title = arguments.get("window_title")
        hwnd = arguments.get("hwnd")
        
        handle = self._get_window_handle(window_title, hwnd)
        if not handle:
            return {
                "success": False,
                "content": None,
                "error": f"未找到窗口: {window_title or hwnd}"
            }
        
        try:
            win32gui.ShowWindow(handle, win32con.SW_MINIMIZE)
            return {
                "success": True,
                "content": {
                    "message": "窗口已最小化",
                    "hwnd": handle
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"最小化窗口失败: {str(e)}"
            }
    
    def _mouse_click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """在指定坐标执行鼠标点击"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pyautogui 未安装，无法执行鼠标点击"
            }
        
        x = arguments.get("x")
        y = arguments.get("y")
        button = arguments.get("button", "left")
        clicks = arguments.get("clicks", 1)
        
        if x is None or y is None:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: x, y"
            }
        
        try:
            # 移动鼠标到指定位置
            pyautogui.moveTo(x, y)
            time.sleep(0.1)
            
            # 执行点击
            pyautogui.click(x, y, clicks=clicks, button=button)
            
            return {
                "success": True,
                "content": {
                    "message": "鼠标点击已执行",
                    "x": x,
                    "y": y,
                    "button": button,
                    "clicks": clicks
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"鼠标点击失败: {str(e)}"
            }
    
    def _keyboard_type(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """模拟键盘输入文本"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pyautogui 未安装，无法执行键盘输入"
            }
        
        text = arguments.get("text")
        interval = arguments.get("interval", 0.01)
        
        if not text:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: text"
            }
        
        try:
            pyautogui.write(text, interval=interval)
            
            return {
                "success": True,
                "content": {
                    "message": "键盘输入已执行",
                    "text": text,
                    "interval": interval
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"键盘输入失败: {str(e)}"
            }
    
    def _keyboard_press(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """模拟按下键盘按键"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "pyautogui 未安装，无法执行键盘按键"
            }
        
        key = arguments.get("key")
        modifiers = arguments.get("modifiers", [])
        
        if not key:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: key"
            }
        
        try:
            # 如果有修饰键，先按下修饰键
            if modifiers:
                pyautogui.hotkey(*modifiers, key)
            else:
                pyautogui.press(key)
            
            return {
                "success": True,
                "content": {
                    "message": "键盘按键已执行",
                    "key": key,
                    "modifiers": modifiers
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"键盘按键失败: {str(e)}"
            }
    
    def _ocr_recognize(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """对指定区域进行OCR文字识别"""
        if not PADDLEOCR_AVAILABLE or not PIL_AVAILABLE:
            return {
                "success": False,
                "content": None,
                "error": "PaddleOCR 或 Pillow 未安装，无法执行OCR识别"
            }
        
        image_path = arguments.get("image_path")
        x = arguments.get("x")
        y = arguments.get("y")
        width = arguments.get("width")
        height = arguments.get("height")
        
        try:
            # 获取图片
            if image_path:
                # 从文件读取
                image = Image.open(image_path)
            else:
                # 从屏幕截图
                if x is None or y is None or width is None or height is None:
                    # 如果没有指定区域，截取整个屏幕
                    if not PYAUTOGUI_AVAILABLE:
                        return {
                            "success": False,
                            "content": None,
                            "error": "pyautogui 未安装，无法截图"
                        }
                    image = pyautogui.screenshot()
                else:
                    if not PYAUTOGUI_AVAILABLE:
                        return {
                            "success": False,
                            "content": None,
                            "error": "pyautogui 未安装，无法截图"
                        }
                    image = pyautogui.screenshot(region=(x, y, width, height))
            
            # 执行OCR
            ocr = self._get_ocr()
            if not ocr:
                return {
                    "success": False,
                    "content": None,
                    "error": "OCR初始化失败"
                }
            
            result = ocr.ocr(image, cls=True)
            
            # 解析结果
            texts = []
            if result and result[0]:
                for line in result[0]:
                    if line:
                        text_info = line[1]
                        text = text_info[0]
                        confidence = text_info[1]
                        texts.append({
                            "text": text,
                            "confidence": float(confidence)
                        })
            
            return {
                "success": True,
                "content": {
                    "texts": texts,
                    "count": len(texts),
                    "full_text": "\n".join([t["text"] for t in texts])
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"OCR识别失败: {str(e)}"
            }
    
    def _shell_execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行shell命令"""
        command = arguments.get("command")
        timeout = arguments.get("timeout", 30)
        cwd = arguments.get("cwd")
        
        if not command:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: command"
            }
        
        try:
            # 在Windows上使用cmd
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                encoding='utf-8',
                errors='ignore'
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return_code = process.returncode
                
                return {
                    "success": return_code == 0,
                    "content": {
                        "stdout": stdout,
                        "stderr": stderr,
                        "return_code": return_code,
                        "command": command
                    },
                    "error": stderr if return_code != 0 else None
                }
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    "success": False,
                    "content": None,
                    "error": f"命令执行超时（{timeout}秒）"
                }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"执行命令失败: {str(e)}"
            }


def create_server(data_dir: str = None) -> SystemServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        SystemServer 实例
    """
    if data_dir:
        config_path = Path(data_dir)
    else:
        # 默认配置目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        config_path = project_root / '.mcp_data' / 'system_tool'
    
    config_path.mkdir(parents=True, exist_ok=True)
    
    return SystemServer(config_path)

