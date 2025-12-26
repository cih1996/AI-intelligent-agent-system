#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试文件
"""

from datetime import datetime
from services.utils.mcp_client import MCPClientManager
import json
from services.simple_client import SimpleAIClient

def main():
    """主函数"""


    ai_client = SimpleAIClient(provider='deepseek',env_file='.env',auto_load_env=True,name="测试AI",prompt_file='prompts/pattern.txt')
    import requests

    url = "http://localhost:5531/api/patterns/ai-analysis?aggregate=true&time_bucket_size_min=30"
    response = requests.get(url)
    response.raise_for_status()
 
    response = ai_client.chat(response.text,max_tokens=1500)
    print(response['content'])
   

if __name__ == "__main__":
    main()

