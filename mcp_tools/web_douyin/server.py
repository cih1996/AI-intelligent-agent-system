#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
抖音网页版 MCP 服务器
符合 MCP 协议标准
"""

import json
import sys
import threading
from pathlib import Path
from typing import Dict, Any

# 添加当前目录到 Python 路径，以便导入同目录下的模块
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from douyin_browser import DouyinBrowser


class DouyinWebServer:
    """抖音网页版工具服务器"""
    
    def __init__(self):
        """初始化服务器"""
        self.browser = None
        self.browser_lock = threading.Lock()
    
    def _get_browser(self) -> DouyinBrowser:
        """
        获取或创建浏览器实例（支持持久化）
        
        Returns:
            DouyinBrowser 实例
        """
        with self.browser_lock:
            if self.browser is None:
                self.browser = DouyinBrowser(headless=False)
                # 不立即打开，等待用户调用 open 工具
            elif not self._is_browser_alive():
                # 浏览器已关闭，重新创建
                try:
                    self.browser.close()
                except:
                    pass
                self.browser = DouyinBrowser(headless=False)
            
            return self.browser
    
    def _is_browser_alive(self) -> bool:
        """
        检查浏览器是否仍然存活
        
        Returns:
            True 如果浏览器存活，False 否则
        """
        if self.browser is None or self.browser.driver is None:
            return False
        
        try:
            # 尝试获取当前窗口句柄，如果失败说明浏览器已关闭
            _ = self.browser.driver.current_window_handle
            return True
        except:
            return False
    
    def _ensure_browser_opened(self) -> bool:
        """
        确保浏览器已打开抖音页面
        
        Returns:
            True 如果成功，False 否则
        """
        browser = self._get_browser()
        
        try:
            # 检查当前 URL 是否是抖音
            current_url = browser.driver.current_url
            if 'douyin.com' not in current_url:
                # 不在抖音页面，打开它
                result = browser.open_douyin()
                return result.get('success', False)
            return True
        except:
            # 浏览器可能已关闭，重新打开
            try:
                result = browser.open_douyin()
                return result.get('success', False)
            except Exception as e:
                print(f"[DouyinWebServer] 打开浏览器失败: {e}", file=sys.stderr)
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
        try:
            if tool_name == "douyin.get_search_results":
                return self._get_search_results(arguments)
            elif tool_name == "douyin.get_video_info":
                return self._get_video_info()
            elif tool_name == "douyin.scroll":
                return self._scroll_video(arguments)
            elif tool_name == "douyin.like":
                return self._like_video()
            elif tool_name == "douyin.get_page_info":
                return self._get_page_info()
            elif tool_name == "douyin.open":
                return self._open_douyin()
            elif tool_name == "douyin.navigate_to_url":
                return self._navigate_to_url(arguments)
            elif tool_name == "douyin.toggle_comments":
                return self._toggle_comments()
            elif tool_name == "douyin.get_comments_list":
                return self._get_comments_list()
            else:
                return {
                    "success": False,
                    "content": None,
                    "error": f"未知工具: {tool_name}"
                }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"工具执行失败: {str(e)}"
            }
    
    def _get_search_results(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """获取搜索结果列表"""
        keyword = arguments.get("keyword")
        if not keyword:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: keyword"
            }
        
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.get_search_results(keyword)
        
        if result.get("success"):
            return {
                "success": True,
                "content": result.get("data", {}),
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "获取搜索结果失败")
            }
    
    def _get_video_info(self) -> Dict[str, Any]:
        """获取视频信息"""
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.get_video_info()
        
        if result.get("success"):
            return {
                "success": True,
                "content": result.get("data", {}),
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "获取视频信息失败")
            }
    
    def _scroll_video(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """滚动视频"""
        direction = arguments.get("direction", "next")
        
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.scroll(direction)
        
        if result.get("success"):
            return {
                "success": True,
                "content": result,
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "滚动失败")
            }
    
    def _like_video(self) -> Dict[str, Any]:
        """点赞视频"""
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.like()
        
        if result.get("success"):
            return {
                "success": True,
                "content": result,
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "点赞失败")
            }
    
    def _get_page_info(self) -> Dict[str, Any]:
        """获取页面信息"""
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.get_page_info()
        
        if result.get("success"):
            return {
                "success": True,
                "content": result.get("data", {}),
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "获取页面信息失败")
            }
    
    def _open_douyin(self) -> Dict[str, Any]:
        """打开抖音"""
        browser = self._get_browser()
        result = browser.open_douyin()
        
        if result.get("success"):
            return {
                "success": True,
                "content": result,
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "打开抖音失败")
            }
    
    def _navigate_to_url(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """跳转到指定URL"""
        url = arguments.get("url")
        if not url:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: url"
            }
        
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.navigate_to_url(url)
        
        if result.get("success"):
            return {
                "success": True,
                "content": result,
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "跳转URL失败")
            }
    
    def _toggle_comments(self) -> Dict[str, Any]:
        """打开/关闭评论区"""
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.toggle_comments()
        
        if result.get("success"):
            return {
                "success": True,
                "content": result,
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "切换评论区失败")
            }
    
    def _get_comments_list(self) -> Dict[str, Any]:
        """获取评论区列表"""
        if not self._ensure_browser_opened():
            return {
                "success": False,
                "content": None,
                "error": "无法打开浏览器"
            }
        
        browser = self._get_browser()
        result = browser.get_comments_list()
        
        if result.get("success"):
            return {
                "success": True,
                "content": result.get("data", {}),
                "error": None
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "获取评论列表失败")
            }


def create_server(data_dir: str = None) -> DouyinWebServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录（可选，当前未使用）
        
    Returns:
        DouyinWebServer 实例
    """
    return DouyinWebServer()

