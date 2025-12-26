#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统信息获取模块
获取已安装应用和当前打开的窗口
"""

import subprocess
import json
import os
from typing import List, Dict, Any
import sys

try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[SystemInfo] 警告: pywin32 未安装，窗口信息获取功能将不可用")


class SystemInfo:
    """系统信息获取类"""
    
    @staticmethod
    def get_installed_apps() -> List[Dict[str, Any]]:
        """
        获取系统已安装的应用列表
        
        Returns:
            应用列表，每个应用包含 name 和 path
        """
        apps = []
        
        try:
            # Windows: 从注册表获取已安装程序
            # 使用 PowerShell 命令获取
            ps_command = """
            Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | 
            Where-Object { $_.DisplayName -ne $null } | 
            Select-Object DisplayName, InstallLocation, Publisher | 
            ConvertTo-Json -Depth 3
            """
            
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        for app in data:
                            if app.get('DisplayName'):
                                apps.append({
                                    "name": app.get('DisplayName', ''),
                                    "path": app.get('InstallLocation', ''),
                                    "publisher": app.get('Publisher', '')
                                })
                    elif isinstance(data, dict):
                        apps.append({
                            "name": data.get('DisplayName', ''),
                            "path": data.get('InstallLocation', ''),
                            "publisher": data.get('Publisher', '')
                        })
                except json.JSONDecodeError:
                    # 如果不是JSON格式，尝试解析文本
                    pass
            
            # 也尝试从开始菜单获取快捷方式
            start_menu_paths = [
                os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
                os.path.join(os.environ.get('PROGRAMDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
            ]
            
            from pathlib import Path
            
            for start_menu_path in start_menu_paths:
                if os.path.exists(start_menu_path):
                    for root, dirs, files in os.walk(start_menu_path):
                        for file in files:
                            if file.endswith('.lnk'):
                                app_name = os.path.splitext(file)[0]
                                # 避免重复
                                if not any(a['name'] == app_name for a in apps):
                                    apps.append({
                                        "name": app_name,
                                        "path": os.path.join(root, file),
                                        "publisher": ""
                                    })
            
        except Exception as e:
            print(f"[SystemInfo] 获取已安装应用失败: {str(e)}")
        
        # 去重（按名称）
        seen = set()
        unique_apps = []
        for app in apps:
            if app['name'] not in seen:
                seen.add(app['name'])
                unique_apps.append(app)
        
        print(f"[SystemInfo] 获取到 {len(unique_apps)} 个已安装应用")
        return unique_apps[:100]  # 限制返回数量，避免token爆炸
    
    @staticmethod
    def get_open_windows() -> List[Dict[str, Any]]:
        """
        获取当前打开的窗口列表（只返回可见窗口）
        
        Returns:
            窗口列表，每个窗口包含 hwnd, title, x, y, width, height
        """
        if not WIN32_AVAILABLE:
            return []
        
        windows = []
        
        def enum_windows_callback(hwnd, windows_list):
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
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
                        
                        # 只返回非最小化的窗口
                        if not is_minimized:
                            windows_list.append({
                                "hwnd": hwnd,
                                "title": title,
                                "x": x,
                                "y": y,
                                "width": width,
                                "height": height,
                                "is_maximized": is_maximized
                            })
                    except Exception as e:
                        pass  # 忽略无法获取信息的窗口
            
            return True
        
        try:
            win32gui.EnumWindows(enum_windows_callback, windows)
        except Exception as e:
            print(f"[SystemInfo] 获取窗口列表失败: {str(e)}")
        
        print(f"[SystemInfo] 获取到 {len(windows)} 个打开的窗口")
        return windows
    
    @staticmethod
    def check_app_exists(app_name: str) -> bool:
        """
        检查指定应用是否存在
        
        Args:
            app_name: 应用名称
            
        Returns:
            是否存在
        """
        apps = SystemInfo.get_installed_apps()
        app_name_lower = app_name.lower()
        
        for app in apps:
            if app_name_lower in app['name'].lower():
                return True
        
        return False

