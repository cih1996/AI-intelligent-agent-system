# MCP Tools 工具集合

这是一个基于 Model Context Protocol (MCP) 标准的工具集合项目。每个文件夹代表一个独立的 MCP 工具插件，可以通过统一的注册中心自动发现和加载。

## 📋 项目结构

```
mcp_tools/
├── registry.py              # MCP 工具注册中心，自动扫描和加载所有插件
├── mcp_server.py            # 标准 MCP 服务器实现（符合 MCP 协议）
├── start.py      # 启动脚本，将 MCP 工具挂载为 HTTP 服务
├── mcp_tester.py           # 交互式测试器，用于手动测试单个 MCP 工具
├── desktop_assistant/      # 桌面操作助手工具
├── system_tool/            # Windows 系统操作工具
├── todo_tool/             # 待办事项管理工具
├── task_tool/             # 任务管理工具
├── memory_tool/           # 记忆管理工具
├── knowledge_tool/         # 知识库工具
├── ui_tool/               # UI 操作工具
├── qq_tool/               # QQ 工具
├── tron_tool/             # Tron 工具
└── web_douyin/            # 抖音网页工具
```

## 🚀 快速开始

### 1. 启动所有 MCP 工具服务器

启动所有已扫描到的 MCP 工具，每个工具会分配不同的端口：

```bash
python start.py --host 0.0.0.0 --base-port 8000
```

**参数说明：**
- `--host`: 监听地址（默认: `127.0.0.1`，使用 `0.0.0.0` 允许外网访问）
- `--base-port`: 基础端口号（默认: `8000`，每个插件会从基础端口开始递增分配）
- `--plugin`: 可选，指定要启动的单个插件名称

**示例：**
```bash
# 启动所有插件
python start.py --host 0.0.0.0 --base-port 8000

# 只启动 system_tool 插件
python start.py --plugin system_tool --host 0.0.0.0 --port 8000
```

启动成功后，每个插件会提供以下 HTTP 端点：
- `http://host:port/health` - 健康检查
- `http://host:port/tools` - 工具列表
- `http://host:port/mcp` - MCP JSON-RPC 端点
- `http://host:port/message` - MCP HTTP 传输端点（用于 Cursor streamable-http）

### 2. 测试 MCP 工具

使用交互式测试器手动测试单个 MCP 工具：

```bash
python mcp_tester.py
```

测试器会：
1. 自动发现所有已启动的 MCP 服务器
2. 列出所有可用工具
3. 交互式输入参数
4. 执行工具并显示结果

**注意：** 使用测试器前，需要先启动 MCP 服务器，并确保 `mcp.json` 配置文件存在且包含服务器配置。

## 📦 核心组件说明

### registry.py - MCP 工具注册中心

`MCPRegistry` 类负责自动扫描和加载所有 MCP 插件：

- **自动扫描**：扫描项目目录下所有包含 `manifest.json` 的文件夹
- **动态加载**：动态导入插件的 `server.py` 并创建服务器实例
- **工具注册**：将每个工具注册到统一的工具注册表中
- **服务器管理**：支持为单个或所有插件启动 HTTP 服务器

**主要方法：**
- `scan_plugins()` - 扫描所有插件
- `load_plugin(plugin_name)` - 加载单个插件
- `load_all_plugins()` - 加载所有插件
- `call_tool(tool_name, arguments)` - 调用工具（本地开发用）
- `start(plugin_name, host, port)` - 启动单个插件的 HTTP 服务器
- `start_all_mcp_servers(host, base_port)` - 启动所有插件的 HTTP 服务器

### mcp_server.py - 标准 MCP 服务器实现

实现了符合 MCP 标准的服务器：

- **MCPServer**：核心 MCP 服务器类，实现 JSON-RPC 2.0 协议
- **HTTPMCPServer**：HTTP 传输的 MCP 服务器，支持部署到外网
- **create_mcp_server_from_plugin()**：从插件信息创建标准 MCP 服务器

**支持的 MCP 方法：**
- `initialize` - 初始化连接
- `tools/list` - 列出所有工具
- `tools/call` - 调用工具
- `ping` - 健康检查

### start.py - 启动脚本

统一的启动入口，支持：
- 启动所有插件或单个插件
- 自定义监听地址和端口
- 自动端口分配

### mcp_tester.py - 交互式测试器

用于手动测试 MCP 工具的功能：
- 列出所有可用的 MCP 服务器
- 选择服务器和工具
- 交互式输入工具参数
- 执行工具并显示结果

## 🔧 开发新的 MCP 工具

要开发新的 MCP 工具，只需在项目根目录下创建一个新文件夹，并包含以下文件：

### 必需文件

#### 1. `manifest.json` - 插件元数据

```json
{
  "name": "your-tool-name",
  "version": "1.0.0",
  "description": "工具描述",
  "entry": "server.py"
}
```

#### 2. `tool.json` - 工具定义

```json
{
  "tools": [
    {
      "name": "your_tool.action",
      "description": "工具功能描述",
      "input_schema": {
        "type": "object",
        "properties": {
          "param1": {
            "type": "string",
            "description": "参数描述"
          }
        },
        "required": ["param1"]
      }
    }
  ]
}
```

#### 3. `server.py` - 服务器实现

必须包含 `create_server()` 函数：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict, Any
from pathlib import Path

class YourToolServer:
    """你的工具服务器"""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        if tool_name == "your_tool.action":
            return self._do_action(arguments)
        else:
            return {
                "success": False,
                "content": None,
                "error": f"未知工具: {tool_name}"
            }
    
    def _do_action(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行操作"""
        param1 = arguments.get("param1")
        
        # 你的业务逻辑
        result = f"处理了: {param1}"
        
        return {
            "success": True,
            "content": result,
            "error": None
        }

def create_server(data_dir: str = None) -> YourToolServer:
    """
    创建服务器实例（MCP 规范要求）
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        YourToolServer 实例
    """
    if data_dir:
        config_path = Path(data_dir)
    else:
        plugin_dir = Path(__file__).parent
        project_root = plugin_dir.parent.parent
        config_path = project_root / '.mcp_data' / 'your_tool'
    
    config_path.mkdir(parents=True, exist_ok=True)
    return YourToolServer(config_path)
```

### 目录结构示例

```
your_tool/
├── manifest.json          # 插件元数据
├── tool.json             # 工具定义
├── server.py             # 服务器实现（必须包含 create_server 函数）
├── config.json           # 可选：配置文件
└── README.md             # 可选：工具说明文档
```

### 工具返回值格式

工具处理函数应返回以下格式的字典：

```python
{
    "success": True,      # 是否成功
    "content": {...},     # 返回内容（可以是字符串、字典、列表等）
    "error": None         # 错误信息（成功时为 None）
}
```

### 自动发现机制

`registry.py` 会自动扫描所有包含 `manifest.json` 的文件夹：
- 扫描项目根目录下的所有子目录
- 检查是否包含 `manifest.json` 文件
- 自动加载 `tool.json` 和 `server.py`
- 调用 `create_server()` 创建服务器实例

**注意：** 文件夹名称不能以 `_` 开头（会被忽略）

## 📝 使用示例

### 示例 1：启动所有工具

```bash
# 启动所有工具，监听 0.0.0.0，从端口 8000 开始
python start.py --host 0.0.0.0 --base-port 8000
```

输出示例：
```
[MCP Registry] 工具目录: D:\工作\Ai\mcp_tools
[MCP Registry] 发现 10 个插件: ['desktop_assistant', 'system_tool', ...]
[MCP Registry] 已加载插件: desktop_assistant (1 个工具)
...
[MCP Server] desktop-assistant v1.0.0 已启动
[MCP Server] HTTP 服务监听: http://0.0.0.0:8000
[MCP Server] 健康检查: http://0.0.0.0:8000/health
[MCP Server] 工具列表: http://0.0.0.0:8000/tools
...
```

### 示例 2：测试工具

```bash
python mcp_tester.py
```

交互流程：
1. 列出所有可用的 MCP 服务器
2. 选择要测试的服务器
3. 列出该服务器的所有工具
4. 选择要测试的工具
5. 输入工具参数
6. 执行工具并查看结果

### 示例 3：通过 HTTP API 调用工具

```bash
# 获取工具列表
curl http://localhost:8000/tools

# 调用工具（JSON-RPC）
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "system.get_windows",
      "arguments": {}
    }
  }'
```

## 🔍 现有工具列表

- **desktop_assistant** - 桌面操作助手，基于 GPT-4o 和 JS 脚本执行引擎
- **system_tool** - Windows 系统操作工具（窗口管理、鼠标键盘、OCR等）
- **todo_tool** - 待办事项管理工具
- **task_tool** - 任务管理工具
- **memory_tool** - 记忆管理工具
- **knowledge_tool** - 知识库工具
- **ui_tool** - UI 操作工具
- **qq_tool** - QQ 工具
- **tron_tool** - Tron 工具
- **web_douyin** - 抖音网页工具

## 📚 技术栈

- **Python 3.x** - 主要开发语言
- **aiohttp** - 异步 HTTP 服务器框架
- **JSON-RPC 2.0** - MCP 协议基于的通信协议
- **Model Context Protocol** - 标准 MCP 协议实现

## 🛠️ 依赖安装

```bash
# 安装核心依赖
pip install aiohttp

# 根据具体工具可能需要安装其他依赖
# 例如 system_tool 需要：
pip install pywin32 pyautogui paddleocr pillow
```

## 🔐 数据隔离机制（系统级参数）

对于需要持久化数据的 MCP 工具（如 `todo_tool`、`memory_tool`），系统支持基于系统级上下文参数的数据隔离，确保多用户使用时数据不会相互干扰。

### MCP 标准实现

按照 MCP 标准，系统级参数应该在 `manifest.json` 中声明，在 `mcp.json` 中配置：

#### 1. 在 `manifest.json` 中声明必需参数

工具开发者需要在 `manifest.json` 中声明 `requiredContext`，告诉 AI 和客户端这个工具需要哪些系统级参数：

```json
{
  "name": "todo-tool",
  "version": "1.0.0",
  "description": "待办事项管理 MCP 工具",
  "entry": "server.py",
  "requiredContext": {
    "user_id": {
      "type": "string",
      "description": "用户ID，用于数据隔离。必须在 mcp.json 中配置",
      "required": true
    }
  }
}
```

**`requiredContext` 字段说明：**
- 键名：参数名称（如 `user_id`、`tenant_id`、`api_key` 等）
- 值：参数定义对象
  - `type`: 参数类型（string, number, boolean 等）
  - `description`: 参数描述
  - `required`: 是否必需（true/false）

#### 2. 在 `mcp.json` 中配置参数

客户端在使用 MCP 工具时，必须在 `mcp.json` 中配置 `requiredContext` 声明的所有必需参数：

```json
{
  "mcpServers": {
    "todo-tool": {
      "url": "http://127.0.0.1:8005",
      "transport": "streamable-http",
      "context": {
        "user_id": "administrator"
      }
    },
    "memory-tool": {
      "url": "http://127.0.0.1:8001",
      "transport": "streamable-http",
      "context": {
        "user_id": "administrator",
        "tenant_id": "company-123",
        "workspace_id": "workspace-456"
      }
    }
  }
}
```

**工作原理：**
1. **声明阶段**：工具在 `manifest.json` 中声明 `requiredContext`，告诉系统需要哪些参数
2. **配置阶段**：用户在 `mcp.json` 中配置这些参数
3. **验证阶段**：客户端在 `initialize` 时，服务器会验证所有必需参数是否提供
4. **隔离阶段**：服务器在会话级别保存上下文，所有工具调用自动使用这些参数进行数据隔离
5. **使用阶段**：工具实现时从 `_context` 参数中提取需要的字段，无需每次传递

**验证机制：**
- 如果 `mcp.json` 中缺少 `requiredContext` 声明的必需参数，服务器会在 `initialize` 时返回错误
- 客户端会显示详细的错误信息，提示需要配置哪些参数

**常见系统级参数示例：**
- `user_id` - 用户ID（数据隔离）
- `tenant_id` - 租户ID（多租户场景）
- `workspace_id` - 工作空间ID
- `api_key` - API密钥（付费/授权MCP）
- `license_key` - 许可证密钥
- 任意其他自定义字段（在 `manifest.json` 中声明即可）

### 向后兼容

系统仍支持旧的配置格式（自动转换为 `context` 对象）：

```json
{
  "mcpServers": {
    "todo-tool": {
      "url": "http://127.0.0.1:8005",
      "transport": "streamable-http",
      "user_id": "administrator"
    }
  }
}
```

**注意：** 如果工具在 `manifest.json` 中声明了 `requiredContext`，建议使用标准的 `context` 对象格式。

### 其他方式（兼容性支持）

系统还支持以下方式传递上下文（优先级从高到低）：

1. **HTTP 请求头**（最高优先级）
   ```bash
   # 使用标准请求头
   curl -X POST http://localhost:8000/mcp \
     -H "X-User-ID: user123" \
     -H "Content-Type: application/json" \
     -d '{...}'
   
   # 使用通用上下文请求头（支持任意字段）
   curl -X POST http://localhost:8000/mcp \
     -H "X-Context-User-Id: user123" \
     -H "X-Context-Tenant-Id: tenant456" \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```

2. **工具参数**（中等优先级）
   ```json
   {
     "method": "tools/call",
     "params": {
       "name": "todo.add",
       "arguments": {
         "title": "任务",
         "user_id": "user123"
       }
     }
   }
   ```

3. **会话级别**（从 `mcp.json` 配置中获取，最低优先级）

### 数据存储结构

启用数据隔离后，数据会按上下文标识存储在独立目录中。默认使用 `user_id` 作为标识：

```
.mcp_data/
├── todo_tool/
│   ├── todos.json              # 默认数据（向后兼容）
│   └── users/
│       ├── administrator/
│       │   └── todos.json      # 用户 administrator 的数据
│       └── user123/
│           └── todos.json      # 用户 user123 的数据
└── memory_tool/
    ├── memory.json             # 默认数据（向后兼容）
    └── users/
        ├── administrator/
        │   └── memory.json     # 用户 administrator 的数据
        └── user123/
            └── memory.json     # 用户 user123 的数据
```

**注意：** 工具实现可以根据需要从 `_context` 中提取任意字段进行数据隔离，不仅限于 `user_id`。例如，可以基于 `tenant_id` 或 `workspace_id` 进行隔离。

### 向后兼容

- **如果没有配置用户标识**：工具会使用默认数据文件（`todos.json`、`memory.json`），保持向后兼容
- **如果配置了用户标识**：工具会为每个用户创建独立的数据目录，实现数据隔离

### 实现数据隔离的工具

目前支持数据隔离的工具：
- ✅ `todo_tool` - 待办事项管理
- ✅ `memory_tool` - 记忆管理

其他需要数据隔离的工具可以按照相同模式实现。

## 📄 许可证

本项目采用 MIT 许可证。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

要添加新的 MCP 工具，只需：
1. 在项目根目录创建新文件夹
2. 添加 `manifest.json`、`tool.json` 和 `server.py`
3. 运行 `start.py` 自动发现和加载

## 📞 支持

如有问题或建议，请提交 Issue。

