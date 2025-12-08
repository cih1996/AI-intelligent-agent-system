#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

// MCP服务器类
class DouyinWebMCPServer {
  constructor() {
    this.server = new Server(
      {
        name: 'douyin-web-mcp',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
    this.transport = new StdioServerTransport();
    this.pythonServerPort = 8765;
    this.pythonServerProcess = null;
    this.ensurePythonServer();
  }

  setupHandlers() {
    // 列出可用工具
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'search_douyin',
          description: '在抖音网页版搜索指定内容并开始自动刷视频',
          inputSchema: {
            type: 'object',
            properties: {
              keyword: {
                type: 'string',
                description: '要搜索的关键词',
              },
            },
            required: ['keyword'],
          },
        },
        {
          name: 'get_video_info',
          description: '获取当前播放视频的信息（播放进度、点赞量、评论数等）',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'auto_scroll',
          description: '自动滚动到下一个视频',
          inputSchema: {
            type: 'object',
            properties: {
              direction: {
                type: 'string',
                enum: ['next', 'prev'],
                description: '滚动方向：next（下一个）或 prev（上一个）',
                default: 'next',
              },
            },
          },
        },
        {
          name: 'like_video',
          description: '点赞当前视频',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'get_page_info',
          description: '获取当前页面的基本信息',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
      ],
    }));

    // 处理工具调用
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case 'search_douyin':
            return await this.handleSearchDouyin(args);
          case 'get_video_info':
            return await this.handleGetVideoInfo();
          case 'auto_scroll':
            return await this.handleAutoScroll(args);
          case 'like_video':
            return await this.handleLikeVideo();
          case 'get_page_info':
            return await this.handleGetPageInfo();
          default:
            throw new Error(`未知的工具: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: 'text',
              text: `错误: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  async handleSearchDouyin(args) {
    const { keyword } = args;
    
    const result = await this.callPythonServer('search', { keyword });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async handleGetVideoInfo() {
    const result = await this.callPythonServer('getVideoInfo');

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async handleAutoScroll(args) {
    const { direction = 'next' } = args || {};
    
    const result = await this.callPythonServer('scroll', { direction });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async handleLikeVideo() {
    const result = await this.callPythonServer('like');

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async handleGetPageInfo() {
    const result = await this.callPythonServer('getPageInfo');

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async ensurePythonServer() {
    // 检查Python服务器是否运行
    try {
      const response = await fetch(`http://localhost:${this.pythonServerPort}/health`);
      if (response.ok) {
        console.error('Python HTTP服务器已在运行');
        return;
      }
    } catch (error) {
      // 服务器未运行，启动它
      console.error('启动Python HTTP服务器...');
      await this.startPythonServer();
    }
  }

  async startPythonServer() {
    const { spawn } = await import('child_process');
    const path = await import('path');
    const { fileURLToPath } = await import('url');
    const os = await import('os');
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);
    
    const scriptPath = path.join(__dirname, 'douyin_server.py');
    const pythonCmd = os.platform() === 'win32' ? 'python' : 'python3';
    
    this.pythonServerProcess = spawn(pythonCmd, [scriptPath, this.pythonServerPort.toString()], {
      cwd: __dirname,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    
    // 等待服务器启动
    await new Promise((resolve) => {
      const checkServer = async () => {
        try {
          const response = await fetch(`http://localhost:${this.pythonServerPort}/health`);
          if (response.ok) {
            console.error('Python HTTP服务器已启动');
            resolve();
            return;
          }
        } catch (error) {
          // 继续等待
        }
        setTimeout(checkServer, 500);
      };
      setTimeout(checkServer, 1000);
    });
  }

  // 通过HTTP调用Python服务器
  async callPythonServer(action, params = {}) {
    // 确保服务器运行
    await this.ensurePythonServer();
    
    const url = new URL(`http://localhost:${this.pythonServerPort}/${action}`);
    
    // 根据action选择GET或POST
    let response;
    if (action === 'search' || action === 'scroll') {
      // POST请求
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
      });
    } else {
      // GET请求
      if (Object.keys(params).length > 0) {
        Object.entries(params).forEach(([key, value]) => {
          url.searchParams.append(key, value);
        });
      }
      response = await fetch(url);
    }
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP请求失败: ${response.status} - ${errorText}`);
    }
    
    const result = await response.json();
    return result;
  }

  async run() {
    await this.server.connect(this.transport);
    console.error('Douyin Web MCP服务器已启动');
  }
}

// 启动服务器
const server = new DouyinWebMCPServer();
server.run().catch(console.error);

