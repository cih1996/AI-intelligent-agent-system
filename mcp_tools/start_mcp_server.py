#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动标准 MCP HTTP 服务器
支持 HTTP 传输方式，可部署到外网
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_tools.registry import MCPRegistry


def main():
    parser = argparse.ArgumentParser(description='启动标准 MCP HTTP 服务器')
    parser.add_argument('--plugin', type=str, help='要启动的插件名称（如果不指定则启动所有插件）')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='监听地址（默认: 127.0.0.1，使用 0.0.0.0 允许外网访问）')
    parser.add_argument('--port', type=int, default=None, help='监听端口（默认: 自动分配）')
    parser.add_argument('--base-port', type=int, default=8000, help='基础端口号（当启动所有插件时使用，默认: 8000）')
    
    args = parser.parse_args()
    
    # 创建注册中心并加载插件
    registry = MCPRegistry()
    registry.load_all_plugins()
    
    # HTTP 模式
    if args.plugin:
        # 启动单个插件的服务器
        if args.plugin not in registry.plugins:
            print(f"错误: 插件 '{args.plugin}' 未加载")
            print(f"可用插件: {', '.join(registry.plugins.keys())}")
            sys.exit(1)
        
        print(f"启动插件 '{args.plugin}' 的 MCP HTTP 服务器...")
        registry.start_mcp_server(args.plugin, host=args.host, port=args.port)
    else:
        # 启动所有插件的服务器
        print(f"启动所有插件的 MCP HTTP 服务器...")
        registry.start_all_mcp_servers(host=args.host, base_port=args.base_port)


if __name__ == '__main__':
    main()

