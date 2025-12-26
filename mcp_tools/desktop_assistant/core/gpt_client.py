#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GPT 客户端模块
独立实现，不依赖外层代码
"""

import requests
import base64
import time
import os
import json
from pathlib import Path
from functools import wraps
from datetime import datetime
from requests.exceptions import (
    SSLError, ConnectionError, Timeout, 
    ProxyError, RequestException
)

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2
RETRY_BACKOFF = 2


def retry_on_network_error(max_retries=MAX_RETRIES, delay=RETRY_DELAY, backoff=RETRY_BACKOFF):
    """网络请求重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            current_delay = delay
            
            while retry_count <= max_retries:
                try:
                    return func(*args, **kwargs)
                except (SSLError, ConnectionError, Timeout, ProxyError) as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"[重试失败] {func.__name__} 达到最大重试次数 {max_retries}")
                        return {
                            "success": False,
                            "message": f"网络请求失败: {str(e)}",
                            "error_type": type(e).__name__,
                            "retries": retry_count - 1
                        }
                    
                    print(f"[重试 {retry_count}/{max_retries}] {func.__name__} 遇到错误: {type(e).__name__}: {str(e)}")
                    print(f"[重试] 等待 {current_delay} 秒后重试...")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
                except Exception as e:
                    print(f"[错误] {func.__name__} 遇到非网络错误: {type(e).__name__}: {str(e)}")
                    return {
                        "success": False,
                        "message": f"请求失败: {str(e)}",
                        "error_type": type(e).__name__
                    }
            
        return wrapper
    return decorator


class GPTClient:
    """GPT-4o 客户端，用于生成和执行脚本"""
    
    def __init__(self, api_key, base_url="https://api.openai.com/v1", model="gpt-4o", use_proxy=False, proxy_url=None, log_dir=None):
        """
        初始化 GPT 客户端
        
        Args:
            api_key: OpenAI API Key
            base_url: API 基础 URL
            model: 使用的模型名称，默认 gpt-4o
            use_proxy: 是否使用代理
            proxy_url: 代理URL
            log_dir: 日志目录路径，用于保存对话历史
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        
        # 日志目录
        if log_dir:
            self.log_dir = Path(log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.log_dir = None
        
        # 配置代理
        if self.use_proxy and self.proxy_url:
            self.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }
        else:
            self.proxies = None
        
        # 请求头
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 请求超时设置（秒）
        self.timeout = 120
        
        # 对话计数器（用于生成唯一ID）
        self.conversation_counter = 0
    
    def encode_image_to_base64(self, image_path):
        """将图片编码为 base64 字符串"""
        try:
            with open(image_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded
        except Exception as e:
            print(f"[错误] 图片编码失败: {str(e)}")
            raise
    
    def get_image_mime_type(self, image_path):
        """获取图片的 MIME 类型"""
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/jpeg')
    
    def _save_conversation_log(self, messages, response, method="chat_with_image", image_path=None):
        """
        保存对话历史到日志文件
        
        Args:
            messages: 发送的消息列表
            response: API响应结果
            method: 调用方法名称
            image_path: 图片路径（如果有）
        """
        if not self.log_dir:
            return
        
        try:
            self.conversation_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 生成日志文件名
            log_filename = f"gpt_conversation_{timestamp}_{self.conversation_counter:04d}.json"
            log_path = self.log_dir / log_filename
            
            # 准备日志数据
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "model": self.model,
                "conversation_id": self.conversation_counter,
                "request": {
                    "messages": self._sanitize_messages_for_log(messages),
                    "image_path": str(image_path) if image_path else None,
                    "image_size": os.path.getsize(image_path) if image_path and os.path.exists(image_path) else None
                },
                "response": {
                    "success": response.get("success", False),
                    "content_length": len(response.get("content", "")) if response.get("content") else 0,
                    "usage": response.get("usage", {}),
                    "error": response.get("message") if not response.get("success") else None
                }
            }
            
            # 如果成功，保存完整内容到单独文件（避免JSON文件过大）
            if response.get("success") and response.get("content"):
                content_filename = f"gpt_content_{timestamp}_{self.conversation_counter:04d}.txt"
                content_path = self.log_dir / content_filename
                with open(content_path, 'w', encoding='utf-8') as f:
                    f.write(response.get("content", ""))
                log_data["response"]["content_file"] = content_filename
            
            # 保存日志
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            print(f"[GPT] 对话日志已保存: {log_filename}")
            
        except Exception as e:
            print(f"[GPT] 保存对话日志失败: {str(e)}")
    
    def _sanitize_messages_for_log(self, messages):
        """
        清理消息内容用于日志（移除base64图片数据，只保留元信息）
        
        Args:
            messages: 原始消息列表
            
        Returns:
            清理后的消息列表
        """
        sanitized = []
        for msg in messages:
            sanitized_msg = {
                "role": msg.get("role"),
                "content": None
            }
            
            content = msg.get("content")
            if isinstance(content, str):
                # 文本内容
                sanitized_msg["content"] = content[:500] + "..." if len(content) > 500 else content
            elif isinstance(content, list):
                # 多模态内容（包含图片）
                sanitized_content = []
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        sanitized_content.append({
                            "type": "text",
                            "text": text[:500] + "..." if len(text) > 500 else text
                        })
                    elif item.get("type") == "image_url":
                        # 图片内容，只保留元信息
                        image_url = item.get("image_url", {})
                        sanitized_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": "[BASE64_IMAGE_DATA]" if image_url.get("url", "").startswith("data:") else image_url.get("url", ""),
                                "detail": image_url.get("detail", "auto")
                            }
                        })
                sanitized_msg["content"] = sanitized_content
            
            sanitized.append(sanitized_msg)
        
        return sanitized
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def chat_with_image(self, image_path, text_prompt, system_prompt=None, max_tokens=4000, temperature=0.7):
        """
        带图片的对话接口
        
        Args:
            image_path: 图片文件路径
            text_prompt: 文本提示词
            system_prompt: 系统提示词
            max_tokens: 最大生成token数
            temperature: 温度参数
            
        Returns:
            生成结果字典
        """
        print(f"[GPT] 开始图片对话...")
        print(f"[GPT] 图片: {image_path}")
        print(f"[GPT] 提示: {text_prompt[:100]}..." if len(text_prompt) > 100 else f"[GPT] 提示: {text_prompt}")
        
        try:
            # 检查图片文件是否存在
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "message": f"图片文件不存在: {image_path}"
                }
            
            # 编码图片
            base64_image = self.encode_image_to_base64(image_path)
            mime_type = self.get_image_mime_type(image_path)
            
            # 构建消息列表
            messages = []
            
            # 添加系统提示词
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            # 构建用户消息内容
            user_content = []
            
            # 添加文本内容
            if text_prompt:
                user_content.append({
                    "type": "text",
                    "text": text_prompt
                })
            
            # 添加图片内容
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}",
                    "detail": "auto"
                }
            })
            
            # 添加用户消息
            user_message = {
                "role": "user",
                "content": user_content
            }
            messages.append(user_message)
            
            # 构建请求体
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                proxies=self.proxies if self.use_proxy else None,
                timeout=self.timeout
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_message = f"API 请求失败，状态码: {response.status_code}"
                try:
                    error_data = response.json()
                    error_message += f"\n错误详情: {error_data.get('error', {}).get('message', '未知错误')}"
                except:
                    error_message += f"\n响应内容: {response.text}"
                
                print(f"[错误] {error_message}")
                return {
                    "success": False,
                    "message": error_message,
                    "status_code": response.status_code
                }
            
            # 解析响应
            result = response.json()
            
            # 提取生成的内容
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                
                # 统计使用的 token
                usage = result.get("usage", {})
                
                print(f"[GPT] 生成完成，Token使用: {usage.get('total_tokens', 0)}")
                
                response_data = {
                    "success": True,
                    "content": content,
                    "usage": usage,
                    "model": self.model
                }
                
                # 保存对话日志
                self._save_conversation_log(messages, response_data, "chat_with_image", image_path)
                
                return response_data
            else:
                error_response = {
                    "success": False,
                    "message": "API 返回数据格式异常",
                    "response": result
                }
                
                # 保存错误日志
                self._save_conversation_log(messages, error_response, "chat_with_image", image_path)
                
                return error_response
                
        except Exception as e:
            print(f"[异常] 图片对话失败: {str(e)}")
            # 保存异常日志
            error_response = {
                "success": False,
                "message": f"异常: {str(e)}",
                "error_type": type(e).__name__
            }
            try:
                self._save_conversation_log(messages, error_response, "chat_with_image", image_path)
            except:
                pass
            raise
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def chat(self, messages, max_tokens=4000, temperature=0.7):
        """
        文本对话接口
        
        Args:
            messages: 消息列表
            max_tokens: 最大生成token数
            temperature: 温度参数
            
        Returns:
            生成结果字典
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                proxies=self.proxies if self.use_proxy else None,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                error_message = f"API 请求失败，状态码: {response.status_code}"
                try:
                    error_data = response.json()
                    error_message += f"\n错误详情: {error_data.get('error', {}).get('message', '未知错误')}"
                except:
                    error_message += f"\n响应内容: {response.text}"
                
                print(f"[错误] {error_message}")
                return {
                    "success": False,
                    "message": error_message,
                    "status_code": response.status_code
                }
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                
                print(f"[GPT] 生成完成，Token使用: {usage.get('total_tokens', 0)}")
                
                response_data = {
                    "success": True,
                    "content": content,
                    "usage": usage,
                    "model": self.model
                }
                
                # 保存对话日志
                self._save_conversation_log(messages, response_data, "chat")
                
                return response_data
            else:
                error_response = {
                    "success": False,
                    "message": "API 返回数据格式异常",
                    "response": result
                }
                
                # 保存错误日志
                self._save_conversation_log(messages, error_response, "chat")
                
                return error_response
                
        except Exception as e:
            print(f"[异常] 聊天请求失败: {str(e)}")
            # 保存异常日志
            error_response = {
                "success": False,
                "message": f"异常: {str(e)}",
                "error_type": type(e).__name__
            }
            try:
                self._save_conversation_log(messages, error_response, "chat")
            except:
                pass
            raise

