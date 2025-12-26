import requests
import base64
import time
import os
import json
from pathlib import Path
from functools import wraps
from requests.exceptions import (
    SSLError, ConnectionError, Timeout, 
    ProxyError, RequestException
)
import sys

# 使用相对导入
from ..utils.image_converter import ImageConverter

# 重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试延迟（秒）
RETRY_BACKOFF = 2  # 退避系数

def retry_on_network_error(max_retries=MAX_RETRIES, delay=RETRY_DELAY, backoff=RETRY_BACKOFF):
    """
    网络请求重试装饰器
    :param max_retries: 最大重试次数
    :param delay: 初始重试延迟（秒）
    :param backoff: 退避系数（每次重试延迟时间乘以此系数）
    """
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
                    current_delay *= backoff  # 指数退避
                    
                except Exception as e:
                    # 其他异常不重试，直接抛出或返回错误
                    print(f"[错误] {func.__name__} 遇到非网络错误: {type(e).__name__}: {str(e)}")
                    return {
                        "success": False,
                        "message": f"请求失败: {str(e)}",
                        "error_type": type(e).__name__
                    }
            
        return wrapper
    return decorator


class DeepSeekClient:
    """
    DeepSeek API 客户端
    支持 DeepSeek 模型，兼容 OpenAI API 格式
    通用的 AI 调用接口，不包含特定业务逻辑
    """
    
    def __init__(
        self, 
        api_key, 
        base_url="https://api.deepseek.com", 
        model="deepseek-chat", 
        use_proxy=False, 
        proxy_url=None
    ):
        """
        初始化 DeepSeek 客户端
        :param api_key: DeepSeek API Key
        :param base_url: API 基础 URL，默认 https://api.deepseek.com
        :param model: 使用的模型名称，默认 deepseek-chat
        :param use_proxy: 是否使用代理
        :param proxy_url: 代理URL（格式：http://host:port 或 https://host:port）
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        
        # 配置代理（如果启用）
        if self.use_proxy and self.proxy_url:
            self.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }
            proxy_info = self.proxy_url
        else:
            self.proxies = None
            proxy_info = "不使用代理"
        
        # 请求头
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 请求超时设置（秒）
        self.timeout = 120

    
    def encode_image_to_base64(self, image_path):
        """
        将图片编码为 base64 字符串
        :param image_path: 图片文件路径
        :return: base64 编码的字符串
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded
        except Exception as e:
            print(f"[错误] 图片编码失败: {str(e)}")
            raise
    
    def get_image_mime_type(self, image_path):
        """
        获取图片的 MIME 类型
        :param image_path: 图片文件路径
        :return: MIME 类型字符串，如 'image/jpeg'
        """
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/jpeg')
    
    def _parse_sse_line(self, line):
        """
        解析 SSE 格式的数据行
        :param line: SSE 数据行
        :return: 解析后的数据字典或 None
        """
        line = line.strip()
        if not line:
            return None
        
        if line.startswith("data: "):
            data_str = line[6:]  # 移除 "data: " 前缀
            if data_str == "[DONE]":
                return {"done": True}
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                return None
        return None
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def chat(
        self, 
        messages, 
        max_tokens=4096, 
        temperature=1.0,
        thinking="disabled",
        frequency_penalty=0,
        presence_penalty=0,
        response_format="text",
        top_p=1.0,
        stream=False,
        stream_options=None,
        callback=None,
        **kwargs
    ):
        """
        通用的聊天接口
        :param messages: 完整的消息列表（已包含系统提示词和历史对话），格式参考 OpenAI API 文档
        :param max_tokens: 最大生成token数，默认 4096
        :param temperature: 温度参数（0-2），默认 1.0
        :param thinking: 思考模式，"enabled" 或 "disabled"，默认 "disabled"
        :param frequency_penalty: 频率惩罚，-2.0 到 2.0，默认 0
        :param presence_penalty: 存在惩罚，-2.0 到 2.0，默认 0
        :param response_format: 响应格式，"text" 或 "json_object"，默认 "text"
        :param top_p: Top-p 采样参数，默认 1.0
        :param stream: 是否开启流式传输，默认 False
        :param stream_options: 流式输出相关选项，字典格式，包含 include_usage (bool)
        :param callback: 流式数据回调函数，接收参数 (chunk_data, accumulated_content)
        :param **kwargs: 其他参数
        :return: 生成结果字典
        """
  
        try:
            # 直接使用传入的完整消息列表（已由 SimpleAIClient 拼接好）
            full_messages = messages
            
            # 构建请求体
            payload = {
                "model": self.model,
                "messages": full_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "thinking": {
                    "type": thinking
                },
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
                "top_p": top_p,
                "stream": stream
            }
            
            # 设置响应格式
            if response_format == "json_object":
                payload["response_format"] = {"type": "json_object"}
            
            # 设置流式选项
            if stream and stream_options:
                payload["stream_options"] = stream_options
            
            # 添加其他参数
            payload.update(kwargs)
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=payload,
                proxies=self.proxies if self.use_proxy else None,
                timeout=self.timeout,
                stream=stream
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
            
            # 处理流式响应
            if stream:
                return self._handle_stream_response(
                    response, 
                    callback
                )
            
            # 处理非流式响应
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                
                #print(f"[成功] 聊天请求完成")
                #print(f"[Token使用] 总计: {usage.get('total_tokens', 0)}")
                
                return {
                    "success": True,
                    "content": content,
                    "usage": usage,
                    "model": self.model,
                    "finish_reason": result["choices"][0].get("finish_reason")
                }
            else:
                return {
                    "success": False,
                    "message": "API 返回数据格式异常",
                    "response": result
                }
                
        except Exception as e:
            print(f"[异常] 聊天请求失败: {str(e)}")
            raise
    
    def _handle_stream_response(self, response, callback):
        """
        处理流式响应
        :param response: requests Response 对象（流式）
        :param callback: 回调函数
        :return: 生成结果字典
        """
        accumulated_content = ""
        finish_reason = None
        usage = None
        model = self.model
        
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                
                # 解析 SSE 数据
                data = self._parse_sse_line(line.decode('utf-8'))
                if not data:
                    continue
                
                # 检查是否结束
                if data.get("done"):
                    break
                
                # 提取数据
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})
                    content_delta = delta.get("content", "")
                    
                    if content_delta:
                        accumulated_content += content_delta
                    
                    # 更新 finish_reason
                    if choice.get("finish_reason"):
                        finish_reason = choice.get("finish_reason")
                    
                    # 更新 model
                    if "model" in data:
                        model = data["model"]
                    
                    # 更新 usage（如果包含）
                    if "usage" in data and data["usage"]:
                        usage = data["usage"]
                    
                    # 调用回调函数
                    if callback and callable(callback):
                        try:
                            callback(data, accumulated_content)
                        except Exception as e:
                            print(f"[警告] 回调函数执行出错: {str(e)}")
            
            return {
                "success": True,
                "content": accumulated_content,
                "usage": usage or {},
                "model": model,
                "finish_reason": finish_reason
            }
            
        except Exception as e:
            print(f"[异常] 流式响应处理失败: {str(e)}")
            return {
                "success": False,
                "message": f"流式响应处理失败: {str(e)}",
                "content": accumulated_content  # 返回已累积的内容
            }
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def chat_with_image(
        self, 
        image_path, 
        text_prompt="", 
        system_prompt=None, 
        max_tokens=4096, 
        temperature=1.0, 
        image_detail="auto",
        thinking="disabled",
        **kwargs
    ):
        """
        通用的图片+文本对话接口
        
        注意：DeepSeek API 目前不支持图片输入，此方法将返回错误提示。
        如果需要处理图片，请使用仅文本的方式描述图片内容。
        
        :param image_path: 图片文件路径（DeepSeek 不支持，此参数将被忽略）
        :param text_prompt: 文本提示词（可选）
        :param system_prompt: 系统提示词（可选，DeepSeek 不支持）
        :param max_tokens: 最大生成token数（DeepSeek 不支持）
        :param temperature: 温度参数（DeepSeek 不支持）
        :param image_detail: 图片细节级别（DeepSeek 不支持，此参数将被忽略）
        :param thinking: 思考模式（DeepSeek 不支持）
        :param **kwargs: 其他参数（DeepSeek 不支持）
        :return: 生成结果字典（包含错误信息）
        """
        # DeepSeek API 不支持图片输入，直接返回错误提示
        print(f"[DeepSeek] 警告: DeepSeek API 不支持图片输入")
        print(f"[DeepSeek] 图片路径: {image_path}")
        print(f"[DeepSeek] 提示: {text_prompt if text_prompt else '无文本提示'}")
        
        return {
            "success": False,
            "message": "DeepSeek API 目前不支持图片输入。请使用纯文本方式描述图片内容，或使用支持图片的模型（如 OpenAI GPT-4 Vision）。",
            "suggestion": "您可以将图片内容转换为文本描述，然后使用 chat() 方法进行对话。"
        }
    
    def analyze_image(
        self, 
        image_path, 
        question=None, 
        max_tokens=4096, 
        temperature=1.0, 
        image_detail="auto",
        thinking="disabled",
        **kwargs
    ):
        """
        分析图片内容（chat_with_image 的便捷方法）
        :param image_path: 图片路径
        :param question: 要问的问题（可选，如果不提供则只发送图片）
        :param max_tokens: 最大生成token数
        :param temperature: 温度参数（0-2）
        :param image_detail: 图片细节级别，"low"、"high" 或 "auto"
        :param thinking: 思考模式，"enabled" 或 "disabled"
        :param **kwargs: 其他参数
        :return: 分析结果字典
        """
        # 调用通用的 chat_with_image 方法
        return self.chat_with_image(
            image_path=image_path,
            text_prompt=question if question else "",
            system_prompt=None,
            max_tokens=max_tokens,
            temperature=temperature,
            image_detail=image_detail,
            thinking=thinking,
            **kwargs
        )
    

