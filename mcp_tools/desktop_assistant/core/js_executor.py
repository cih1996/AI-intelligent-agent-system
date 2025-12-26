#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JS脚本执行引擎
执行GPT生成的JS代码，并提供Python函数接口
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import time

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[JSExecutor] 警告: pyautogui 未安装，鼠标和键盘操作功能将不可用")

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("[JSExecutor] 警告: PaddleOCR 未安装，OCR功能将不可用")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[JSExecutor] 警告: Pillow 未安装，OCR功能将不可用")

try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[JSExecutor] 警告: pywin32 未安装，窗口操作功能将不可用")


class JSExecutor:
    """JS脚本执行引擎"""
    
    def __init__(self, screenshot_manager=None, system_info=None, comm_dir=None):
        """
        初始化JS执行引擎
        
        Args:
            screenshot_manager: 截图管理器实例
            system_info: 系统信息实例
            comm_dir: 通信目录（用于Python和JS之间的文件通信）
        """
        self.screenshot_manager = screenshot_manager
        self.system_info = system_info
        self.execution_log = []
        self._ocr = None
        
        # 通信目录
        if comm_dir:
            self.comm_dir = Path(comm_dir)
        else:
            import tempfile
            self.comm_dir = Path(tempfile.gettempdir()) / "desktop_assistant" / "comm"
        
        self.comm_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前执行会话ID（用于隔离不同执行）
        self.session_id = None
    
    def _get_ocr(self):
        """获取OCR实例（延迟初始化）"""
        if not PADDLEOCR_AVAILABLE:
            return None
        
        if self._ocr is None:
            try:
                self._ocr = PaddleOCR(use_angle_cls=True, lang='ch')
            except Exception as e:
                print(f"[JSExecutor] OCR初始化失败: {e}")
                return None
        
        return self._ocr
    
    def _log(self, message: str):
        """记录执行日志"""
        log_entry = {
            "timestamp": time.time(),
            "message": message
        }
        self.execution_log.append(log_entry)
        print(f"[JS执行] {message}")
    
    def _call_python_function(self, func_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        从JS调用Python函数
        
        Args:
            func_name: 函数名称
            args: 函数参数
            
        Returns:
            函数执行结果
        """
        self._log(f"调用Python函数: {func_name}({json.dumps(args, ensure_ascii=False)})")
        
        try:
            if func_name == 'capture_region_ocr':
                return self._capture_region_ocr(args)
            elif func_name == 'check_app_exists':
                return self._check_app_exists(args)
            elif func_name == 'open_app_and_wait':
                return self._open_app_and_wait(args)
            elif func_name == 'mouse_click':
                return self._mouse_click(args)
            elif func_name == 'keyboard_type':
                return self._keyboard_type(args)
            elif func_name == 'keyboard_press':
                return self._keyboard_press(args)
            elif func_name == 'get_top_window':
                return self._get_top_window(args)
            else:
                return {
                    "success": False,
                    "error": f"未知函数: {func_name}"
                }
        except Exception as e:
            self._log(f"函数执行失败: {func_name} - {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _capture_region_ocr(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """截取区域并OCR识别"""
        if not PYAUTOGUI_AVAILABLE or not PIL_AVAILABLE:
            return {
                "success": False,
                "error": "pyautogui 或 Pillow 未安装"
            }
        
        x = args.get('x', 0)
        y = args.get('y', 0)
        width = args.get('width', 100)
        height = args.get('height', 100)
        
        try:
            # 截取区域
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            # OCR识别
            ocr = self._get_ocr()
            if not ocr:
                return {
                    "success": False,
                    "error": "OCR初始化失败"
                }
            
            result = ocr.ocr(screenshot, cls=True)
            
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
                "texts": texts,
                "full_text": "\n".join([t["text"] for t in texts])
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _check_app_exists(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """检查应用是否存在"""
        app_name = args.get('appName', '')
        if not app_name:
            return {
                "success": False,
                "error": "缺少参数: appName"
            }
        
        exists = self.system_info.check_app_exists(app_name) if self.system_info else False
        
        return {
            "success": True,
            "exists": exists
        }
    
    def _open_app_and_wait(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """打开应用并等待窗口"""
        app_name = args.get('appName', '')
        window_title = args.get('windowTitle', '')
        timeout = args.get('timeout', 10000)  # 毫秒
        
        if not app_name:
            return {
                "success": False,
                "error": "缺少参数: appName"
            }
        
        try:
            # 尝试通过开始菜单启动
            import subprocess
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            
            # 等待窗口出现
            if window_title and WIN32_AVAILABLE:
                start_time = time.time()
                while (time.time() - start_time) * 1000 < timeout:
                    def enum_windows_callback(hwnd, windows):
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if window_title.lower() in title.lower():
                                windows.append(hwnd)
                        return True
                    
                    windows = []
                    win32gui.EnumWindows(enum_windows_callback, windows)
                    
                    if windows:
                        return {
                            "success": True,
                            "hwnd": windows[0],
                            "window_title": win32gui.GetWindowText(windows[0])
                        }
                    
                    time.sleep(0.5)
            
            return {
                "success": True,
                "message": "应用已启动（未检测到窗口）"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _mouse_click(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """鼠标点击"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "error": "pyautogui 未安装"
            }
        
        x = args.get('x')
        y = args.get('y')
        button = args.get('button', 'left')
        clicks = args.get('clicks', 1)
        
        if x is None or y is None:
            return {
                "success": False,
                "error": "缺少参数: x, y"
            }
        
        try:
            pyautogui.moveTo(x, y)
            time.sleep(0.1)
            pyautogui.click(x, y, clicks=clicks, button=button)
            
            return {
                "success": True,
                "message": f"已点击 ({x}, {y})"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _keyboard_type(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """键盘输入"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "error": "pyautogui 未安装"
            }
        
        text = args.get('text', '')
        interval = args.get('interval', 0.01)
        
        if not text:
            return {
                "success": False,
                "error": "缺少参数: text"
            }
        
        try:
            pyautogui.write(text, interval=interval)
            return {
                "success": True,
                "message": f"已输入文本: {text[:50]}..."
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _keyboard_press(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """键盘按键"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "error": "pyautogui 未安装"
            }
        
        key = args.get('key', '')
        modifiers = args.get('modifiers', [])
        
        if not key:
            return {
                "success": False,
                "error": "缺少参数: key"
            }
        
        try:
            if modifiers:
                pyautogui.hotkey(*modifiers, key)
            else:
                pyautogui.press(key)
            
            return {
                "success": True,
                "message": f"已按下按键: {key}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_top_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """获取顶层窗口"""
        if not WIN32_AVAILABLE:
            return {
                "success": False,
                "error": "pywin32 未安装"
            }
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            
            return {
                "success": True,
                "hwnd": hwnd,
                "title": title,
                "x": x,
                "y": y,
                "width": right - x,
                "height": bottom - y
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _handle_python_call(self, request_id: str, func_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理来自JS的Python函数调用请求
        
        Args:
            request_id: 请求ID
            func_name: 函数名称
            args: 函数参数
            
        Returns:
            函数执行结果
        """
        try:
            result = self._call_python_function(func_name, args)
            
            # 写入响应文件
            response_file = self.comm_dir / f"response_{request_id}.json"
            with open(response_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e)
            }
            response_file = self.comm_dir / f"response_{request_id}.json"
            with open(response_file, 'w', encoding='utf-8') as f:
                json.dump(error_result, f, ensure_ascii=False, indent=2)
            return error_result
    
    def _monitor_requests(self, timeout: float = 60.0):
        """
        监控JS的Python函数调用请求（在后台线程运行）
        
        Args:
            timeout: 超时时间（秒）
        """
        import threading
        
        def monitor():
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # 查找请求文件
                    request_files = list(self.comm_dir.glob(f"request_{self.session_id}_*.json"))
                    
                    for request_file in request_files:
                        try:
                            # 读取请求
                            with open(request_file, 'r', encoding='utf-8') as f:
                                request_data = json.load(f)
                            
                            request_id = request_data.get('request_id')
                            func_name = request_data.get('func')
                            args = request_data.get('args', {})
                            
                            # 处理请求
                            self._handle_python_call(request_id, func_name, args)
                            
                            # 删除请求文件
                            try:
                                request_file.unlink()
                            except:
                                pass
                                
                        except Exception as e:
                            print(f"[JSExecutor] 处理请求失败: {str(e)}")
                    
                    time.sleep(0.1)  # 轮询间隔
                    
                except Exception as e:
                    print(f"[JSExecutor] 监控请求失败: {str(e)}")
                    time.sleep(0.5)
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        return monitor_thread
    
    def execute_js(self, js_code: str) -> Dict[str, Any]:
        """
        执行JS代码（使用Node.js，通过文件与Python通信）
        
        Args:
            js_code: JS代码字符串
            
        Returns:
            执行结果
        """
        self._log("开始执行JS代码")
        self.execution_log = []  # 清空日志
        
        # 生成会话ID
        self.session_id = f"session_{int(time.time() * 1000)}_{os.getpid()}"
        
        try:
            # 读取JS函数库
            js_functions_path = Path(__file__).parent.parent / "js_functions" / "base.js"
            with open(js_functions_path, 'r', encoding='utf-8') as f:
                js_functions_code = f.read()
            
            # 创建临时JS文件
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "desktop_assistant"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            temp_js_file = temp_dir / f"script_{self.session_id}.js"
            
            # 构建桥接代码（使用文件通信）
            comm_dir_str = str(self.comm_dir).replace('\\', '\\\\')
            bridge_code = f"""
            const fs = require('fs');
            const path = require('path');
            
            // 通信目录
            const COMM_DIR = {json.dumps(str(self.comm_dir))};
            const SESSION_ID = {json.dumps(self.session_id)};
            
            // 同步调用Python函数（阻塞等待）
            function __callPythonFunctionSync(funcName, args) {{
                const requestId = `${{SESSION_ID}}_${{Date.now()}}_${{Math.random().toString(36).substr(2, 9)}}`;
                const requestFile = path.join(COMM_DIR, `request_${{requestId}}.json`);
                const responseFile = path.join(COMM_DIR, `response_${{requestId}}.json`);
                
                // 写入请求
                const request = {{
                    request_id: requestId,
                    func: funcName,
                    args: args || {{}}
                }};
                
                try {{
                    fs.writeFileSync(requestFile, JSON.stringify(request, null, 2), 'utf8');
                }} catch (error) {{
                    return {{success: false, error: `写入请求失败: ${{error.message}}`}};
                }}
                
                // 等待响应（轮询）
                const maxWait = 30000; // 最大等待30秒
                const pollInterval = 50; // 每50ms检查一次
                const startTime = Date.now();
                
                while (Date.now() - startTime < maxWait) {{
                    try {{
                        if (fs.existsSync(responseFile)) {{
                            // 读取响应
                            const responseData = fs.readFileSync(responseFile, 'utf8');
                            const response = JSON.parse(responseData);
                            
                            // 删除响应文件
                            try {{
                                fs.unlinkSync(responseFile);
                            }} catch (e) {{
                                // 忽略删除错误
                            }}
                            
                            return response;
                        }}
                    }} catch (error) {{
                        // 继续等待
                    }}
                    
                    // 等待一段时间
                    const waitStart = Date.now();
                    while (Date.now() - waitStart < pollInterval) {{
                        // 忙等待
                    }}
                }}
                
                // 超时
                try {{
                    if (fs.existsSync(requestFile)) {{
                        fs.unlinkSync(requestFile);
                    }}
                }} catch (e) {{
                    // 忽略
                }}
                
                return {{success: false, error: '等待Python响应超时'}};
            }}
            
            // 异步调用Python函数
            async function __callPythonFunction(funcName, args) {{
                return __callPythonFunctionSync(funcName, args);
            }}
            
            // 日志函数
            function __log(message) {{
                const logMsg = {{
                    type: 'log',
                    message: String(message),
                    timestamp: Date.now()
                }};
                console.error(JSON.stringify(logMsg));
            }}
            
            // 注入JS函数库
            {js_functions_code}
            
            // 用户代码
            (async function() {{
                try {{
                    {js_code}
                }} catch (error) {{
                    __log(`执行错误: ${{error.message}}`);
                    const errorMsg = {{
                        type: 'error',
                        error: error.message,
                        stack: error.stack
                    }};
                    console.error(JSON.stringify(errorMsg));
                }}
            }})();
            """
            
            # 写入临时文件
            with open(temp_js_file, 'w', encoding='utf-8') as f:
                f.write(bridge_code)
            
            # 启动请求监控线程（在JS执行期间和之后继续运行）
            monitor_thread = self._monitor_requests(timeout=120)  # 延长超时，确保处理完所有请求
            
            self._log("JS代码已准备，开始执行...")
            self._log(f"通信目录: {self.comm_dir}")
            self._log(f"会话ID: {self.session_id}")
            
            # 执行Node.js
            import subprocess
            result = subprocess.run(
                ['node', str(temp_js_file)],
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='ignore'
            )
            
            # JS执行完成后，等待一小段时间确保所有请求都被处理
            time.sleep(0.5)
            
            # 解析输出
            error_lines = result.stderr.split('\n')
            
            # 处理日志
            for line in error_lines:
                if line.strip():
                    try:
                        log_data = json.loads(line)
                        if log_data.get('type') == 'log':
                            self._log(log_data.get('message', ''))
                        elif log_data.get('type') == 'error':
                            self._log(f"JS错误: {log_data.get('error', '')}")
                    except:
                        pass
            
            # 清理临时文件
            try:
                temp_js_file.unlink()
            except:
                pass
            
            # 清理通信文件
            try:
                for comm_file in self.comm_dir.glob(f"*_{self.session_id}_*"):
                    try:
                        comm_file.unlink()
                    except:
                        pass
            except:
                pass
            
            if result.returncode == 0:
                self._log("JS代码执行完成")
                return {
                    "success": True,
                    "output": result.stdout,
                    "log": self.execution_log
                }
            else:
                self._log(f"JS执行失败: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout,
                    "log": self.execution_log
                }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Node.js未安装或不在PATH中",
                "log": self.execution_log
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "JS执行超时",
                "log": self.execution_log
            }
        except Exception as e:
            self._log(f"JS执行失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "log": self.execution_log
            }
    
    def get_execution_log(self) -> list:
        """获取执行日志"""
        return self.execution_log.copy()
    
    def clear_log(self):
        """清空执行日志"""
        self.execution_log = []

