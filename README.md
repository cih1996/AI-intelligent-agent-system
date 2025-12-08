# 🤖 AI 智能体助手系统

一个基于多Agent架构的智能助手系统，集成了多种MCP（Model Context Protocol）工具，通过AI Agents协作完成复杂任务。

> 💡 小提示：主包投入 $200 让 Claude 开发了本 MPC + 多 AI 智能体系统并开放源码，目前为第一版。后续将计划加入网页端、完善更多 MCP 功能，实现更多畅想中的特性，敬请期待！

## ✨ 项目特性

- 🧠 **多Agent架构**：主脑、监督、路由、执行、记忆管理五大AI Agent协同工作
- 🔧 **MCP工具集成**：支持多种工具插件（QQ、抖音、待办、记忆、知识库等）
- 🎯 **智能任务分解**：自动将用户意图分解为可执行的任务序列
- 🔒 **安全审核机制**：多层安全审核确保操作安全合规
- 💾 **记忆管理**：持久化用户记忆，提供个性化服务
- 🌐 **多模型支持**：支持OpenAI、DeepSeek
- 📊 **完整日志**：每个Agent独立日志，便于调试和追踪

## 📁 项目目录结构

```
Ai/
├── ai_agents/                    # AI Agent模块
│   ├── base_agent.py            # Agent基类
│   ├── main_brain_agent.py      # 主脑AI（任务规划）
│   ├── supervisor_agent.py      # 监督AI（安全审核）
│   ├── router_agent.py          # 路由AI（工具选择）
│   ├── executor_agent.py        # 执行AI（工具调用）
│   └── memory_manager_agent.py # 记忆管理AI
│
├── ai_client/                    # AI客户端模块
│   ├── simple_client.py         # 统一AI客户端
│   └── aiServices/              # 各AI服务实现
│       ├── openai.py            # OpenAI服务
│       └── deepseek.py          # DeepSeek服务
│
├── mcp_tools/                    # MCP工具插件目录
│   ├── registry.py               # 工具注册中心
│   ├── qq_tool/                 # QQ工具（消息、空间动态）
│   ├── web_douyin/              # 抖音网页版工具
│   ├── todo_tool/               # 待办事项工具
│   ├── memory_tool/             # 记忆工具
│   ├── knowledge_tool/          # 知识库工具
│   ├── task_tool/               # 任务管理工具
│   ├── ui_tool/                 # UI操作工具
│   └── system_tool/             # 系统工具
│
├── prompts/                      # AI提示词模板
│   ├── example.txt              # 主脑AI提示词
│   ├── mcp_supervisor.txt       # 监督AI提示词
│   ├── mcp_tool_router.txt      # 路由AI提示词
│   ├── mcp_tool_executor.txt    # 执行AI提示词
│   └── mcp_memory_manager.txt   # 记忆管理AI提示词
│
├── utils/                        # 工具模块
│   └── mcp_client.py            # MCP客户端管理器
│
├── logs/                         # 日志目录
│   └── *.log                    # 各Agent的日志文件
│
├── .mcp_data/                   # MCP数据目录
│   ├── user_memory.txt          # 用户记忆文件
│   └── [tool_name]/             # 各工具的数据文件
│
├── core_logic.py                # 核心业务逻辑
├── main.py                      # 主入口文件
├── mcp_tester.py                # MCP工具测试器
├── mcp.json                     # MCP服务器配置
├── requirements.txt             # Python依赖
└── README.md                    # 项目说明文档
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

编辑 `mcp.json` 配置MCP服务器地址：

```json
{
  "mcpServers": {
    "qq-tool": {
      "url": "http://127.0.0.1:8002",
      "transport": "streamable-http"
    },
    "web-douyin": {
      "url": "http://127.0.0.1:8007",
      "transport": "streamable-http"
    }
  }
}
```

### 5. 启动系统

```bash
#启动MCP服务
python mcp_tools/start_mcp_server.py

#启动AI对话(如MCP未启动将无法获得MCP能力)
python main.py
```

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

## 🔧 MCP工具说明

### QQ工具 (qq_tool)

- **功能**：QQ消息发送、空间动态发布
- **工具**：
  - `qq.get_recent_contact` - 获取最近消息列表
  - `qq.send_group_msg` - 发送群聊消息
  - `qq.send_private_msg` - 发送私聊消息
  - `qq.publish_qzone` - 发表QQ空间动态

### 抖音工具 (web_douyin)

- **功能**：抖音网页版自动化操作
- **工具**：
  - `douyin.open` - 打开抖音网页版
  - `douyin.search` - 搜索视频
  - `douyin.get_video_info` - 获取视频信息
  - `douyin.scroll` - 切换视频
  - `douyin.like` - 点赞视频
  - `douyin.get_comments_list` - 获取评论列表

### 待办工具 (todo_tool)

- **功能**：待办事项管理
- **工具**：
  - `todo.add` - 添加待办
  - `todo.update` - 更新待办
  - `todo.list` - 列出待办
  - `todo.remove` - 删除待办

### 记忆工具 (memory_tool)

- **功能**：记忆存储和检索
- **工具**：
  - `memory.save` - 保存记忆
  - `memory.search` - 搜索记忆
  - `memory.delete` - 删除记忆

### 知识库工具 (knowledge_tool)

- **功能**：知识库管理
- **工具**：
  - `knowledge.add` - 添加知识
  - `knowledge.search` - 搜索知识
  - `knowledge.update` - 更新知识

## 🤖 AI Agents说明

### 1. MainBrainAgent（主脑AI）

- **职责**：理解用户意图，生成任务执行计划
- **输入**：用户自然语言消息
- **输出**：ActionSpec JSON格式的任务计划
- **提示词**：`prompts/example.txt`

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

### 示例1：发送QQ消息

```
用户：帮我给群123456发送消息"大家好"
系统：
1. 主脑AI理解意图 → 生成发送QQ群消息的任务
2. 监督AI审核 → 通过
3. 路由AI选择 → qq_tool
4. 执行AI调用 → qq.send_group_msg(group_id="123456", message="大家好")
5. 返回结果 → 消息发送成功
```

### 示例2：搜索抖音视频

```
用户：帮我搜索"Python教程"相关的视频
系统：
1. 主脑AI理解意图 → 生成搜索抖音视频的任务
2. 监督AI审核 → 通过
3. 路由AI选择 → web_douyin工具
4. 执行AI调用 → douyin.get_search_results(keyword="Python教程")
5. 返回结果 → 视频列表
```

### 示例3：管理待办事项

```
用户：添加一个待办：明天完成项目报告
系统：
1. 主脑AI理解意图 → 生成添加待办的任务
2. 监督AI审核 → 通过
3. 路由AI选择 → todo_tool
4. 执行AI调用 → todo.add(title="完成项目报告", due_date="明天")
5. 返回结果 → 待办已添加
```

## 🧪 测试工具

项目提供了MCP工具测试器，可以单独测试每个工具：

```bash
python mcp_tester.py
```

功能特性：
- 🔍 自动扫描所有MCP插件
- 📋 列出插件的所有工具
- 📝 自动解析工具参数schema
- ⌨️ 交互式参数输入
- ✅ 实时执行并显示结果

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

### 添加新的MCP工具

1. 在 `mcp_tools/` 目录下创建工具目录
2. 创建 `manifest.json`、`tool.json` 和 `server.py`
3. 在 `mcp.json` 中配置服务器地址
4. 重启系统即可使用

### 自定义AI Agent

1. 继承 `BaseAgent` 类
2. 实现 `chat()` 方法
3. 在 `ai_agents/__init__.py` 中注册
4. 在 `core_logic.py` 中集成

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题或建议，请通过Issue反馈。

---

**注意**：使用本系统时请遵守相关平台的使用条款，不要进行违法违规操作。
