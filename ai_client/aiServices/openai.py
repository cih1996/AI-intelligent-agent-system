import requests
import base64
import time
import os
from pathlib import Path
from functools import wraps
from requests.exceptions import (
    SSLError, ConnectionError, Timeout, 
    ProxyError, RequestException
)
import sys
from pathlib import Path

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


class OpenAIClient:
    """
    OpenAI API 客户端
    支持多种 GPT 模型，可进行文本对话和图片理解
    通用的 AI 调用接口，不包含特定业务逻辑
    """
    
    # 模型价格表（每百万 tokens 的价格，单位：美元）
    MODEL_PRICES = {
        "gpt-5.1": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
        "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
        "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "cached_input": 0.025, "output": 0.40},
        "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
        "gpt-4o-2024-05-13": {"input": 5.00, "cached_input": 0, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
        "gpt-realtime": {"input": 4.00, "cached_input": 0.40, "output": 16.00},
        "gpt-realtime-mini": {"input": 0.60, "cached_input": 0.06, "output": 2.40},
        "gpt-4o-realtime-preview": {"input": 5.00, "cached_input": 2.50, "output": 20.00},
        "gpt-4o-mini-realtime-preview": {"input": 0.60, "cached_input": 0.30, "output": 2.40},
        "gpt-audio": {"input": 2.50, "cached_input": 0, "output": 10.00},
        "gpt-audio-mini": {"input": 0.60, "cached_input": 0, "output": 2.40},
        "gpt-4o-audio-preview": {"input": 2.50, "cached_input": 0, "output": 10.00},
        "gpt-4o-mini-audio-preview": {"input": 0.15, "cached_input": 0, "output": 0.60},
    }
    
    @staticmethod
    def calculate_cost(model, usage):
        """
        计算 API 调用成本
        :param model: 模型名称
        :param usage: token 使用量字典 (包含 prompt_tokens, completion_tokens 等)
        :return: dict 包含详细费用信息
        """
        if model not in OpenAIClient.MODEL_PRICES:
            return {
                "success": False,
                "message": f"未找到模型 {model} 的价格信息"
            }
        
        prices = OpenAIClient.MODEL_PRICES[model]
        
        # 获取 token 数量
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)
        
        # 检查是否有缓存的 tokens
        prompt_tokens_details = usage.get('prompt_tokens_details', {})
        cached_tokens = prompt_tokens_details.get('cached_tokens', 0)
        
        # 计算实际输入 tokens（非缓存）
        input_tokens = prompt_tokens - cached_tokens
        
        # 计算费用（价格是每百万 tokens）
        input_cost = (input_tokens * prices['input']) / 1_000_000
        cached_cost = (cached_tokens * prices['cached_input']) / 1_000_000
        output_cost = (completion_tokens * prices['output']) / 1_000_000
        total_cost = input_cost + cached_cost + output_cost
        
        return {
            "success": True,
            "model": model,
            "tokens": {
                "input": input_tokens,
                "cached": cached_tokens,
                "output": completion_tokens,
                "total": total_tokens
            },
            "costs": {
                "input": input_cost,
                "cached": cached_cost,
                "output": output_cost,
                "total": total_cost
            },
            "prices": prices
        }
    
    def __init__(self, api_key, base_url="https://api.openai.com/v1", model="gpt-4o-mini", use_proxy=False, proxy_url=None):
        """
        初始化 OpenAI 客户端
        :param api_key: OpenAI API Key
        :param base_url: API 基础 URL（可以是官方或其他兼容的端点）
        :param model: 使用的模型名称，默认 gpt-4o-mini
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
        
        # 对话历史记录
        self.conversation_history = []

    
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
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def chat_with_image(self, image_path, text_prompt="", system_prompt=None, max_tokens=500, temperature=0.7, image_detail="auto", use_history=True, history_messages=None):
        """
        通用的图片+文本对话接口
        :param image_path: 图片文件路径
        :param text_prompt: 文本提示词（可选，如果为空则只发送图片）
        :param system_prompt: 系统提示词（可选）
        :param max_tokens: 最大生成token数
        :param temperature: 温度参数（0-2），越高越随机
        :param image_detail: 图片细节级别，"low"、"high" 或 "auto"
        :param use_history: 是否使用历史对话记录（默认True）
        :param history_messages: 外部传入的历史对话记录（可选，如果不提供则使用内部存储的历史）
        :return: 生成结果字典
        """
        print(f"[OpenAI] 开始图片对话...")
        print(f"[OpenAI] 图片: {image_path}")
        if text_prompt:
            print(f"[OpenAI] 提示: {text_prompt}")
        if system_prompt:
            print(f"[OpenAI] 使用系统提示词: {len(system_prompt)} 字符")
        
        try:
            # 检查图片文件是否存在
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "message": f"图片文件不存在: {image_path}"
                }
            
            # 使用图片转换器转换图片格式
            print(f"[OpenAI] 转换图片格式...")
            convert_result = ImageConverter.convert_to_png(image_path, keep_original=True)
            
            if not convert_result["success"]:
                return {
                    "success": False,
                    "message": f"图片转换失败: {convert_result['message']}"
                }
            
            # 使用转换后的图片路径
            processed_image_path = convert_result["output_path"]
            is_converted = not convert_result.get("is_original", False)
            
            if is_converted:
                print(f"[OpenAI] 图片已转换: {processed_image_path}")
                print(f"[OpenAI] 原始大小: {convert_result['original_size']} bytes")
                print(f"[OpenAI] 转换后大小: {convert_result['new_size']} bytes")
            else:
                print(f"[OpenAI] 图片已是PNG格式，无需转换")
            
            # 编码图片
            base64_image = self.encode_image_to_base64(processed_image_path)
            mime_type = self.get_image_mime_type(processed_image_path)
            
            # 构建消息列表
            messages = []
            
            # 构建完整的消息列表（包含历史对话）
            full_messages = []
            
            if use_history:
                # 如果提供了外部历史，使用外部历史；否则使用内部存储的历史
                history = history_messages if history_messages is not None else self.conversation_history
                # 合并历史对话
                full_messages.extend(history)
            
            # 如果提供了系统提示词，添加到消息列表（只在当前消息中添加，不重复添加历史中的system）
            if system_prompt:
                # 检查历史中是否已有system消息
                has_system = any(msg.get("role") == "system" for msg in full_messages)
                if not has_system:
                    full_messages.append({
                        "role": "system",
                        "content": system_prompt
                    })
            
            # 构建用户消息内容
            user_content = []
            
            # 如果有文本提示词，添加文本内容
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
                    "detail": image_detail
                }
            })
            
            # 添加用户消息
            user_message = {
                "role": "user",
                "content": user_content
            }
            full_messages.append(user_message)
            
            # 构建请求体
            payload = {
                "model": self.model,
                "messages": full_messages,
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
                
                #print(f"[成功] 图片对话完成")
                #print(f"[内容] {content[:100]}..." if len(content) > 100 else f"[内容] {content}")
                #print(f"[Token使用] 提示: {usage.get('prompt_tokens', 0)}, "
                #      f"完成: {usage.get('completion_tokens', 0)}, "
                #      f"总计: {usage.get('total_tokens', 0)}")
                
                # 计算费用
                cost_info = self.calculate_cost(self.model, usage)
                if cost_info["success"]:
                    costs = cost_info["costs"]
                    print(f"[费用] 输入: ${costs['input']:.6f}, "
                          f"输出: ${costs['output']:.6f}, "
                          f"总计: ${costs['total']:.6f} USD")
                
                # 如果使用历史记录，自动保存对话到历史
                if use_history and history_messages is None:
                    # 只有当使用内部历史记录时，才自动保存
                    # 如果使用外部历史记录，不自动保存（由调用者自己管理）
                    # 添加用户消息到历史（包含图片信息，但为了节省空间，只保存文本提示词）
                    user_history_message = {
                        "role": "user",
                        "content": text_prompt if text_prompt else "[图片消息]"
                    }
                    self.conversation_history.append(user_history_message)
                    
                    # 添加AI回复到历史
                    assistant_message = {
                        "role": "assistant",
                        "content": content
                    }
                    self.conversation_history.append(assistant_message)
                
                # 清理转换后的临时文件（如果有转换的话）
                if is_converted and processed_image_path != image_path:
                    try:
                        if os.path.exists(processed_image_path):
                            os.remove(processed_image_path)
                            print(f"[清理] 已删除临时转换文件: {processed_image_path}")
                    except Exception as e:
                        print(f"[警告] 清理临时文件失败: {str(e)}")
                
                return {
                    "success": True,
                    "content": content,
                    "usage": usage,
                    "cost": cost_info if cost_info["success"] else None,
                    "model": self.model
                }
            else:
                return {
                    "success": False,
                    "message": "API 返回数据格式异常",
                    "response": result
                }
                
        except Exception as e:
            print(f"[异常] 图片对话失败: {str(e)}")
            raise
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def chat(self, messages, max_tokens=500, temperature=0.7, use_history=True, history_messages=None):
        """
        通用的聊天接口
        :param messages: 消息列表，格式参考 OpenAI API 文档
        :param max_tokens: 最大生成token数
        :param temperature: 温度参数（0-2）
        :param use_history: 是否使用历史对话记录（默认True）
        :param history_messages: 外部传入的历史对话记录（可选，如果不提供则使用内部存储的历史）
        :return: 生成结果字典
        """
  
        try:
            # 构建完整的消息列表（包含历史对话）
            full_messages = []
            
            if use_history:
                # 如果提供了外部历史，使用外部历史；否则使用内部存储的历史
                history = history_messages if history_messages is not None else self.conversation_history
                # 合并历史对话和当前消息
                full_messages.extend(history)
            
            # 添加当前消息
            full_messages.extend(messages)
            
            payload = {
                "model": self.model,
                "messages": full_messages,
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

                #print(f"[Token使用] 总计: {usage.get('total_tokens', 0)}")
                
                # 计算费用
                cost_info = self.calculate_cost(self.model, usage)
                #if cost_info["success"]:
                    #print(f"[费用] 总计: ${cost_info['costs']['total']:.6f} USD")
                
                # 如果使用历史记录，自动保存对话到历史
                if use_history and history_messages is None:
                    # 只有当使用内部历史记录时，才自动保存
                    # 如果使用外部历史记录，不自动保存（由调用者自己管理）
                    # 添加用户消息到历史
                    for msg in messages:
                        if msg.get("role") in ["user", "assistant", "system"]:
                            self.conversation_history.append(msg.copy())
                    
                    # 添加AI回复到历史
                    assistant_message = {
                        "role": "assistant",
                        "content": content
                    }
                    self.conversation_history.append(assistant_message)
                
                return {
                    "success": True,
                    "content": content,
                    "usage": usage,
                    "cost": cost_info if cost_info["success"] else None,
                    "model": self.model
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
    
    @retry_on_network_error(max_retries=3, delay=2, backoff=2)
    def analyze_image(self, image_path, question=None, max_tokens=500, temperature=0.7, image_detail="auto", use_history=True, history_messages=None):
        """
        分析图片内容（chat_with_image 的便捷方法）
        :param image_path: 图片路径
        :param question: 要问的问题（可选，如果不提供则只发送图片）
        :param max_tokens: 最大生成token数
        :param temperature: 温度参数（0-2）
        :param image_detail: 图片细节级别，"low"、"high" 或 "auto"
        :param use_history: 是否使用历史对话记录（默认True）
        :param history_messages: 外部传入的历史对话记录（可选，如果不提供则使用内部存储的历史）
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
            use_history=use_history,
            history_messages=history_messages
        )
    
    def get_conversation_history(self):
        """
        获取完整的对话历史记录
        :return: 对话历史列表，包含所有用户和AI的消息
        """
        return self.conversation_history.copy()
    
    def clear_conversation_history(self):
        """
        清空对话历史记录
        """
        self.conversation_history = []
        print(f"[OpenAI] 对话历史已清空")
    
    def add_to_history(self, role, content):
        """
        手动添加消息到对话历史
        :param role: 消息角色，"user"、"assistant" 或 "system"
        :param content: 消息内容
        """
        if role not in ["user", "assistant", "system"]:
            raise ValueError(f"无效的角色: {role}，必须是 'user'、'assistant' 或 'system'")
        
        message = {
            "role": role,
            "content": content
        }
        self.conversation_history.append(message)
        print(f"[OpenAI] 已添加 {role} 消息到历史记录")


