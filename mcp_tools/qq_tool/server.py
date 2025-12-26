#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
QQ 工具 MCP 服务器
符合 MCP 协议标准
"""

import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlencode, quote


class QQServer:
    """QQ 工具服务器"""
    
    def __init__(self, data_dir: Path):
        """
        初始化服务器
        
        Args:
            data_dir: 数据存储目录（基础目录）
        """
        self.data_dir = data_dir
        # token 和 host 从系统级参数中获取，不在这里初始化
        self.api_base_url = None
        self.token = None
    
    def _make_request(self, endpoint: str, method: str = "POST", data: Optional[Dict[str, Any]] = None, api_base_url: str = None, token: str = None) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            endpoint: API端点（如 "/get_recent_contact"）
            method: HTTP方法（GET/POST）
            data: 请求数据
            api_base_url: API基础URL（从系统级参数获取）
            token: 认证token（从系统级参数获取）
            
        Returns:
            响应结果字典
        """
        if not api_base_url or not token:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需的配置参数: host 或 token。请在 mcp.json 中配置 context.host 和 context.token"
            }
        
        # 确保URL不以斜杠结尾
        api_base_url = api_base_url.rstrip('/')
        url = f"{api_base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer "+token
        }
        try:
            if method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=30)
            else:
                response = requests.get(url, params=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # 检查API响应状态
            if result.get("status") == "ok" and result.get("retcode") == 0:
                return {
                    "success": True,
                    "content": result.get("data"),
                    "error": None
                }
            else:
                error_msg = result.get("message") or result.get("wording") or "API返回错误"
                return {
                    "success": False,
                    "content": None,
                    "error": f"API错误: {error_msg}"
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "content": None,
                "error": f"请求失败: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "content": None,
                "error": f"响应解析失败: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"未知错误: {str(e)}"
            }
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数（包含 _context 上下文对象，由 mcp_server.py 自动注入）
            
        Returns:
            工具执行结果
        """
        # 从上下文对象中提取系统级参数（从 mcp.json 配置中获取）
        context = arguments.get('_context', {})
        token = context.get('token')
        host = context.get('host')
        
        # 校验必需的上下文参数（根据 manifest.json 中的 requiredContext）
        if not token:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需的上下文参数: token。请在 ai/mcp.json 中配置 context.token"
            }
        
        if not host:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需的上下文参数: host。请在 ai/mcp.json 中配置 context.host"
            }
        
        # 从参数中移除 _context，避免传递给具体的方法
        arguments = {k: v for k, v in arguments.items() if k != '_context'}
        
        if tool_name == "qq.get_recent_contact":
            return self._get_recent_contact(arguments, host, token)
        elif tool_name == "qq.send_group_msg":
            return self._send_group_msg(arguments, host, token)
        elif tool_name == "qq.send_private_msg":
            return self._send_private_msg(arguments, host, token)
        elif tool_name == "qq.publish_qzone":
            return self._publish_qzone(arguments, host, token)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _get_recent_contact(self, arguments: Dict[str, Any], api_base_url: str, token: str) -> Dict[str, Any]:
        """获取最近消息列表"""
        count = arguments.get("count", 10)
        
        data = {
            "count": count
        }
        
        return self._make_request("/get_recent_contact", "POST", data, api_base_url, token)
    
    def _send_group_msg(self, arguments: Dict[str, Any], api_base_url: str, token: str) -> Dict[str, Any]:
        """发送群聊消息"""
        group_id = arguments.get("group_id")
        message = arguments.get("message")
        
        if not group_id:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: group_id"
            }
        
        if not message:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: message"
            }
        
        # 将纯文本消息转换为API需要的格式
        message_array = [
            {
                "type": "text",
                "data": {
                    "text": message
                }
            }
        ]
        
        data = {
            "group_id": group_id,
            "message": message_array
        }
        
        return self._make_request("/send_group_msg", "POST", data, api_base_url, token)
    
    def _send_private_msg(self, arguments: Dict[str, Any], api_base_url: str, token: str) -> Dict[str, Any]:
        """发送私聊消息"""
        user_id = arguments.get("user_id")
        message = arguments.get("message")
        
        if not user_id:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: user_id"
            }
        
        if not message:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: message"
            }
        
        # 将纯文本消息转换为API需要的格式
        message_array = [
            {
                "type": "text",
                "data": {
                    "text": message
                }
            }
        ]
        
        data = {
            "user_id": user_id,
            "message": message_array
        }
        
        return self._make_request("/send_private_msg", "POST", data, api_base_url, token)
    
    def _get_cookies(self, api_base_url: str, token: str) -> Dict[str, Any]:
        """
        获取QQ cookies
        
        Args:
            api_base_url: API基础URL
            token: 认证token
        
        Returns:
            包含cookies和bkn的字典，如果失败返回None
        """
        data = {
            "domain": "qzone.qq.com"
        }
        
        result = self._make_request("/get_cookies", "POST", data, api_base_url, token)
        
        if result.get("success"):
            return result.get("content")
        else:
            return None
    
    def _parse_cookies(self, cookies_str: str) -> Dict[str, str]:
        """
        解析cookie字符串为字典
        
        Args:
            cookies_str: cookie字符串，如 "uin=o0276265453; skey=@JxKN9nmnf; ..."
            
        Returns:
            cookie字典
        """
        cookies = {}
        try:
            for item in cookies_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
        except Exception as e:
            print(f"[QQServer] 解析cookie失败: {e}")
        return cookies
    
    def _extract_qq_from_cookie(self, cookies_str: str) -> Optional[str]:
        """
        从cookie字符串中提取QQ号
        
        Args:
            cookies_str: cookie字符串，如 "uin=o0276265453; skey=..."
            
        Returns:
            QQ号字符串，如果提取失败返回None
        """
        try:
            cookies = self._parse_cookies(cookies_str)
            
            # 获取uin
            uin = cookies.get('uin', '')
            if not uin:
                return None
            
            # 去掉前面的o（如果有）
            if uin.startswith('o'):
                uin = uin[1:]
            
            # 去掉开头的0（如果有）
            qq = uin.lstrip('0')
            
            # 如果全部是0，返回原始值
            if not qq:
                qq = uin
            
            return qq
        except Exception as e:
            print(f"[QQServer] 提取QQ号失败: {e}")
            return None
    
    def _extract_pskey_from_cookie(self, cookies_str: str) -> Optional[str]:
        """
        从cookie字符串中提取p_skey（完整值，不去掉@符号）
        
        Args:
            cookies_str: cookie字符串，如 "uin=o0276265453; p_skey=@JxKN9nmnf; ..."
            
        Returns:
            p_skey字符串（完整值），如果提取失败返回None
        """
        try:
            cookies = self._parse_cookies(cookies_str)
            p_skey = cookies.get('p_skey', '')
            if not p_skey:
                return None
            
            # 直接返回完整的p_skey，不去掉@符号
            return p_skey
        except Exception as e:
            print(f"[QQServer] 提取p_skey失败: {e}")
            return None
    
    def _calculate_g_tk(self, p_skey: str) -> int:
        """
        计算g_tk值
        
        Args:
            p_skey: p_skey字符串（完整值，可能包含@符号）
            
        Returns:
            g_tk整数值
        """
        hash_value = 5381
        for char in p_skey:
            hash_value += (hash_value << 5) + ord(char)
        return hash_value & 2147483647
    
    def _publish_qzone(self, arguments: Dict[str, Any], api_base_url: str, token: str) -> Dict[str, Any]:
        """发表QQ空间动态"""
        content = arguments.get("content")
        
        if not content:
            return {
                "success": False,
                "content": None,
                "error": "缺少必需参数: content"
            }
        
        # 获取cookies
        cookies_data = self._get_cookies(api_base_url, token)
        if not cookies_data:
            return {
                "success": False,
                "content": None,
                "error": "获取cookies失败"
            }
        
        cookies_str = cookies_data.get("cookies")
        
        if not cookies_str:
            return {
                "success": False,
                "content": None,
                "error": "cookies数据为空"
            }
        
        # 提取QQ号
        hostuin = self._extract_qq_from_cookie(cookies_str)
        if not hostuin:
            return {
                "success": False,
                "content": None,
                "error": "无法从cookie中提取QQ号"
            }
        
        # 提取p_skey并计算g_tk
        p_skey = self._extract_pskey_from_cookie(cookies_str)
        if not p_skey:
            return {
                "success": False,
                "content": None,
                "error": "无法从cookie中提取p_skey"
            }
        
        g_tk = self._calculate_g_tk(p_skey)
        
        # 构建表单数据
        form_data = {
            "syn_tweet_verson": "1",
            "paramstr": "1",
            "pic_template": "",
            "richtype": "",
            "richval": "",
            "special_url": "",
            "subrichtype": "",
            "who": "1",
            "con": content,  # 发表内容
            "feedversion": "1",
            "ver": "1",
            "ugc_right": "1",
            "to_sign": "0",
            "hostuin": hostuin,  # 当前登录的QQ
            "code_version": "1",
            "format": "fs",
            "qzreferrer": f"https://user.qzone.qq.com/{hostuin}"
        }
        
        # URL编码表单数据
        form_data_encoded = urlencode(form_data, encoding='utf-8')
        
        # 构建URL（使用计算出的g_tk）
        url = f"https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6?&g_tk={g_tk}"
        
        # 设置请求头
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Cookie": cookies_str,
            "Referer": f"https://user.qzone.qq.com/{hostuin}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            response = requests.post(url, data=form_data_encoded, headers=headers, timeout=30)
            
            # 只要HTTP状态码是200就认为成功，不检查响应体
            response.raise_for_status()
            
            return {
                "success": True,
                "content": {
                    "message": "发表成功",
                    "status_code": response.status_code
                },
                "error": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "content": None,
                "error": f"请求失败: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": f"未知错误: {str(e)}"
            }


def create_server(data_dir: str = None) -> QQServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        QQServer 实例
    """
    if data_dir:
        data_path = Path(data_dir)
    else:
        # 默认数据目录
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        data_path = project_root / '.mcp_data' / 'qq_tool'
    
    data_path.mkdir(parents=True, exist_ok=True)
    
    return QQServer(data_path)

