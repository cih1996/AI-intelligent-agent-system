# 🤖 AI 智能体助手系统

作为开发者，我打造这个项目的初衷，是希望通过多Agent协作架构帮助大家更直观、低门槛地体验和开发MCP（Model Context Protocol）相关能力。系统集成了多种MCP工具，能够让AI Agents分工协作完成复杂任务。这样不仅能促进更多人理解AI多模态的实际应用方式，也为MCP生态的未来发展和多模态AI的落地提供了探索和参考，让更多开发者能够轻松上手MCP、发挥其在各类场景中的潜力。

> 💡 小提示：主包投入 $200 让 Claude 开发了本 MCP + 多 AI 智能体系统并开放源码，目前为第一版。后续将计划加入网页端、完善更多 MCP 功能，实现更多畅想中的特性，敬请期待！

## 🏗️ 项目架构

本项目采用**双项目独立架构**：

- **`ai/`** - AI智能体系统：多Agent协作框架，负责理解用户意图、任务规划、工具调用
- **`mcp_tools/`** - MCP工具集合：独立的MCP工具插件集合，每个工具可独立部署为HTTP服务
- **`web/`** - 可视化网页面板: 独立的网页对话面板,可接入`ai`接口,配置mcp等操作

三个项目完全独立，通过HTTP协议通信，符合MCP标准。

## ✨ 项目特性

- 🧠 **多Agent架构**：主脑、监督、路由、执行、记忆管理五大AI Agent协同工作
- 🔧 **MCP工具集成**：支持标准MCP协议，可集成任意MCP工具插件
- 🎯 **智能任务分解**：自动将用户意图分解为可执行的任务序列
- 🔒 **安全审核机制**：多层安全审核确保操作安全合规
- 💾 **记忆管理**：持久化用户记忆，提供个性化服务
- 🌐 **多模型支持**：支持OpenAI、DeepSeek等多种AI模型
- 📊 **完整日志**：每个Agent独立日志，便于调试和追踪
- 🔐 **系统级参数**：支持数据隔离、授权验证等系统级参数配置

## 📁 项目目录结构

本项目包含两个独立的子项目：

### 1. AI 智能体系统 (`ai/`)

独立的智能体系统项目，负责多Agent协作和MCP工具调用。



```
ai/
├── agents/                    # AI Agent模块
│   ├── __init__.py
│   ├── executor_agent.py        # 执行AI（工具调用）
│   ├── main_brain_agent.py      # 主脑AI（任务规划）
│   ├── memory_manager_agent.py  # 记忆管理AI
│   ├── router_agent.py          # 路由AI（工具选择）
│   └── supervisor_agent.py      # 监督AI（安全审核）
│
├── ai_client/                    # AI客户端模块
│   ├── __init__.py
│   ├── simple_client.py         # 统一AI客户端
│   └── aiServices/              # 各AI服务实现
│       ├── __init__.py
│       ├── openai.py            # OpenAI服务
│       └── deepseek.py          # DeepSeek服务
│
├── prompts/                      # AI提示词模板
│   ├── mcp_context_compressor.txt    # 上下文压缩提示词
│   ├── mcp_main_brain.txt            # 主脑AI提示词
│   ├── mcp_memory_manager.txt         # 记忆管理AI提示词
│   ├── mcp_supervisor.txt             # 监督AI提示词
│   ├── mcp_tool_executor.txt          # 执行AI提示词
│   └── mcp_tool_router.txt            # 路由AI提示词
│
├── utils/                        # 工具模块
│   ├── __init__.py
│   └── mcp_client.py            # MCP客户端管理器（调用MCP工具）
│
├── conversations/                # 对话历史目录
│   ├── 主脑AI/                  # 主脑AI对话历史
│   ├── 执行AI/                  # 执行AI对话历史
│   ├── 监督AI/                  # 监督AI对话历史
│   ├── 路由AI/                  # 路由AI对话历史
│   └── 记忆管理AI/              # 记忆管理AI对话历史
│
├── logs/                         # 日志目录
│   └── *.log                    # 各Agent的日志文件
│
├── core_logic.py                # 核心业务逻辑
├── main.py                      # 主入口文件
├── mcp.json                     # MCP服务器配置（配置要调用的MCP工具）
└── requirements.txt             # Python依赖
```

### 2. MCP 工具集合 (`mcp_tools/`)

独立的MCP工具项目，提供各种MCP工具插件，每个工具可独立部署为HTTP服务。

```
mcp_tools/
├── registry.py                   # MCP工具注册中心（自动扫描和加载插件）
├── mcp_server.py                 # 标准MCP服务器实现（HTTP传输）
├── start.py                      # 启动脚本（启动所有MCP工具服务）
├── mcp_tester.py                # MCP工具测试器
├── README.MD                    # MCP工具项目说明文档
│
├── [tool_name]/                 # 各个MCP工具插件目录
│   ├── manifest.json            # 工具元数据（声明requiredContext等）
│   ├── tool.json                # 工具定义（工具列表和参数schema）
│   ├── server.py                # 工具服务器实现（必须包含create_server函数）
│   └── [其他文件]               # 工具特定的配置文件等
│
└── 示例工具：
    ├── todo_tool/               # 待办事项工具（示例）
    ├── memory_tool/             # 记忆工具（示例）
    ├── knowledge_tool/          # 知识库工具（示例）
    ├── system_tool/             # 系统操作工具（示例）
    ├── qq_tool/                 # QQ工具（示例）
    ├── web_douyin/              # 抖音网页工具（示例）
    └── ...                      # 更多工具
```



## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Chrome浏览器（用于抖音工具）
- Node.js（可选，用于部分工具）

### 2. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装抖音工具依赖（可选）
cd mcp_tools/web_douyin
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件并配置AI模型API密钥：

```env
# OpenAI配置
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_USE_PROXY=false
OPENAI_PROXY_URL=http://127.0.0.1:7890

# DeepSeek配置
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_USE_PROXY=false
DEEPSEEK_PROXY_URL=http://127.0.0.1:7890
```

### 4. 配置MCP工具

编辑 `ai/mcp.json` 配置要调用的MCP服务器地址：

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
        "user_id": "administrator"
      }
    }
  }
}
```

**配置说明：**
- `url`: MCP服务器的HTTP地址
- `transport`: 传输方式（固定为 `streamable-http`）
- `context`: 系统级上下文参数（如 `user_id`、`api_key` 等），用于数据隔离和授权
  - 这些参数会在 `initialize` 时自动传递给MCP服务器
  - 每个工具可以在 `manifest.json` 中声明 `requiredContext` 来要求必需参数

### 5. 启动系统

**步骤1：启动MCP工具服务**

```bash
# 进入MCP工具目录
cd mcp_tools

# 启动所有MCP工具服务（每个工具监听不同端口）
python start.py --host 0.0.0.0 --base-port 8000

# 或启动单个工具
python start.py --plugin todo_tool --host 0.0.0.0 --port 8005
```

**步骤2：启动AI智能体系统**

```bash
# 进入AI项目目录
cd ai

# 启动AI对话系统
python main.py
```

**注意：** 必须先启动MCP工具服务，AI系统才能调用MCP能力。

## 📊 系统执行流程

```
┌─────────────────┐
│   用户输入       │
│ （自然语言消息） │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│   MainBrainAgent    │
│    （主脑AI）        │
│  理解用户意图       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ MemoryManagerAgent   │
│ （记忆管理AI）       │
│  读取用户记忆        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   MainBrainAgent     │
│   生成任务计划       │
│ （ActionSpec JSON）  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  SupervisorAgent     │
│   （监督AI）         │
│  安全合规审核        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   RouterAgent       │
│   （路由AI）         │
│  选择合适的工具      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  ExecutorAgent       │
│   （执行AI）         │
│  确定工具参数        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   MCP工具插件        │
│  执行具体操作        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   工具返回结果       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  ExecutorAgent       │
│  结果归并整合        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  SupervisorAgent     │
│  最终安全检查        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   MainBrainAgent     │
│  生成最终回复        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   返回给用户         │
└─────────────────────┘
```

## 🔧 MCP工具开发

### MCP工具标准结构

每个MCP工具插件需要包含以下文件：

1. **`manifest.json`** - 工具元数据
   ```json
   {
     "name": "tool-name",
     "version": "1.0.0",
     "description": "工具描述",
     "entry": "server.py",
     "requiredContext": {
       "user_id": {
         "type": "string",
         "description": "用户ID，用于数据隔离",
         "required": true
       }
     }
   }
   ```

2. **`tool.json`** - 工具定义（给AI看的工具列表和参数）
   ```json
   {
     "tools": [
       {
         "name": "tool.action",
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

3. **`server.py`** - 工具服务器实现
   - 必须包含 `create_server()` 函数
   - 实现 `call_tool()` 方法处理工具调用
   - 从 `arguments['_context']` 中提取系统级参数（如 `user_id`）

### 系统级参数机制

- **声明**：在 `manifest.json` 的 `requiredContext` 中声明必需的系统级参数
- **配置**：在 `ai/mcp.json` 的 `context` 中配置这些参数
- **传递**：AI系统在 `initialize` 时自动传递 `context` 给MCP服务器
- **使用**：工具的 `server.py` 从 `arguments['_context']` 中提取参数并自行校验

### 开发新工具

1. 在 `mcp_tools/` 目录下创建工具目录
2. 创建 `manifest.json`、`tool.json` 和 `server.py`
3. 在 `ai/mcp.json` 中配置服务器地址和 `context`
4. 启动MCP服务即可使用

详细开发指南请参考 `mcp_tools/README.MD`

## 🤖 AI Agents说明

### 1. MainBrainAgent（主脑AI）

- **职责**：理解用户意图，生成任务执行计划
- **输入**：用户自然语言消息
- **输出**：ActionSpec JSON格式的任务计划
- **提示词**：`prompts/mcp_main_brain.txt`

### 2. SupervisorAgent（监督AI）

- **职责**：审核任务计划的安全性和合规性
- **检查项**：
  - 操作是否安全
  - 是否符合规范
  - 参数是否合理
- **提示词**：`prompts/mcp_supervisor.txt`

### 3. RouterAgent（路由AI）

- **职责**：为任务选择合适的MCP工具
- **功能**：
  - 分析任务需求
  - 匹配可用工具
  - 选择最佳工具
- **提示词**：`prompts/mcp_tool_router.txt`

### 4. ExecutorAgent（执行AI）

- **职责**：执行工具调用，生成具体参数
- **功能**：
  - 确定工具方法
  - 生成调用参数
  - 执行工具调用
  - 处理返回结果
- **提示词**：`prompts/mcp_tool_executor.txt`

### 5. MemoryManagerAgent（记忆管理AI）

- **职责**：管理和更新用户记忆
- **功能**：
  - 读取用户记忆
  - 更新记忆内容
  - 记忆持久化
- **提示词**：`prompts/mcp_memory_manager.txt`

## 💡 使用示例

### 示例：管理待办事项

```
用户：添加一个待办：明天完成项目报告

系统执行流程：
1. 主脑AI理解意图 → 生成添加待办的任务（ActionSpec JSON）
2. 监督AI审核 → 检查任务安全性和合理性
3. 路由AI选择 → 匹配到 todo_tool 工具
4. 执行AI调用 → todo.add(title="完成项目报告", due_date="明天")
   - MCP客户端自动从 ai/mcp.json 读取 context.user_id
   - 在 initialize 时传递给MCP服务器
   - MCP服务器保存到会话级别
   - 工具调用时自动注入到 arguments['_context']
   - todo_tool/server.py 从 _context 提取 user_id 进行数据隔离
5. 返回结果 → 待办已添加（数据保存在 .mcp_data/todo_tool/users/{user_id}/todos.json）
```

## 🧪 测试工具

### MCP工具测试器

MCP工具项目提供了测试器，可以单独测试每个工具：

```bash
# 进入MCP工具目录
cd mcp_tools

# 运行测试器（需要先启动MCP服务）
python mcp_tester.py
```

功能特性：
- 🔍 自动扫描所有已启动的MCP服务器
- 📋 列出服务器的所有工具
- 📝 自动解析工具参数schema
- ⌨️ 交互式参数输入
- ✅ 实时执行并显示结果

### AI系统测试

```bash
# 进入AI项目目录
cd ai

# 运行主程序进行对话测试
python main.py
```

## 📝 日志系统

每个AI Agent都有独立的日志文件，保存在 `logs/` 目录：

- `主脑ai_YYYYMMDD_HHMMSS.log` - 主脑AI日志
- `监督ai_YYYYMMDD_HHMMSS.log` - 监督AI日志
- `路由ai_YYYYMMDD_HHMMSS.log` - 路由AI日志
- `执行ai_YYYYMMDD_HHMMSS.log` - 执行AI日志
- `记忆管理ai_YYYYMMDD_HHMMSS.log` - 记忆管理AI日志

## 🔐 安全机制

1. **多层审核**：每个任务都经过监督AI审核
2. **参数验证**：执行前验证所有参数
3. **操作记录**：所有操作都有日志记录
4. **错误处理**：完善的异常处理机制

## 🛠️ 开发指南

### 开发新的MCP工具

参考 `mcp_tools/README.MD` 中的详细开发指南：

1. 在 `mcp_tools/` 目录下创建工具目录
2. 创建 `manifest.json`（声明 `requiredContext` 如果需要）
3. 创建 `tool.json`（定义工具列表和参数）
4. 创建 `server.py`（实现工具逻辑，从 `_context` 提取系统级参数）
5. 在 `ai/mcp.json` 中配置服务器地址和 `context`
6. 启动MCP服务即可使用

### 自定义AI Agent

1. 在 `ai/agents/` 目录下创建新的Agent类
2. 实现必要的接口方法
3. 在 `ai/core_logic.py` 中集成到工作流

### 系统级参数配置

- **数据隔离**：在 `manifest.json` 中声明 `requiredContext.user_id`，在 `ai/mcp.json` 中配置
- **授权验证**：在 `manifest.json` 中声明 `requiredContext.api_key`，在 `ai/mcp.json` 中配置
- **多租户**：可以声明 `tenant_id`、`workspace_id` 等参数

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题或建议，请通过Issue反馈。

---

**注意**：使用本系统时请遵守相关平台的使用条款，不要进行违法违规操作。
