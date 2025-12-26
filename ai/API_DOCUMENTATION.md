# AI 对话服务 API 文档

## 概述

本服务提供 HTTP REST API 接口，使用 Server-Sent Events (SSE) 推送实时状态更新。

- **基础 URL**: `http://localhost:5001`
- **协议**: HTTP/1.1, Server-Sent Events (SSE)

---

## 目录

1. [聊天接口](#聊天接口)
2. [REST API 接口](#rest-api-接口)
3. [数据结构说明](#数据结构说明)
4. [错误处理](#错误处理)
5. [示例代码](#示例代码)

---

## 聊天接口

### 发送消息

**接口**: `POST /api/chat`

**Content-Type**: `application/json`

**请求体**:
```json
{
  "history_file": "string",  // 对话会话ID（必需）
  "message": "string"        // 用户消息内容（必需）
}
```

**说明**:
- `history_file`: 对话会话的唯一标识符，用于维护对话上下文
- `message`: 用户输入的消息内容

**响应**: Server-Sent Events (SSE) 流式响应

**Content-Type**: `text/event-stream`

**响应格式**: SSE 格式，每行以 `data: ` 开头，后跟 JSON 数据

---

### SSE 事件类型

#### 1. `chat_callback` - 状态更新

AI 思考、回复或错误信息

**数据格式**:
```json
{
  "type": "chat_callback",
  "callback_type": "thinking" | "reply" | "error",
  "content": "string"
}
```

**字段说明**:
- `callback_type`: 
  - `thinking`: AI 正在思考，`content` 为思考过程描述
  - `reply`: AI 的最终回复，`content` 为回复内容
  - `error`: 发生错误，`content` 为错误信息

**SSE 格式示例**:
```
data: {"type":"chat_callback","callback_type":"thinking","content":"正在思考.."}

data: {"type":"chat_callback","callback_type":"thinking","content":"正在搜索MCP工具"}

data: {"type":"chat_callback","callback_type":"reply","content":"这是AI的回复内容"}

```

#### 2. `response` - 最终响应

消息处理完成后的最终响应

**数据格式**:
```json
{
  "type": "response",
  "data": {
    "success": true,
    "response": "string",    // AI 的最终回复内容
    "actions": [             // 执行的 actions 列表
      {
        "type": "reply" | "mcp",
        "payload": "string"
      }
    ]
  }
}
```

**字段说明**:
- `success`: 是否成功
- `response`: AI 的最终回复文本
- `actions`: 执行的 action 列表
  - `type`: action 类型
    - `reply`: 文本回复
    - `mcp`: MCP 工具调用
  - `payload`: action 的具体内容

**SSE 格式示例**:
```
data: {"type":"response","data":{"success":true,"response":"我已经帮你完成了任务","actions":[{"type":"reply","payload":"我已经帮你完成了任务"}]}}

```

#### 3. `error` - 错误响应

处理失败时发送

**数据格式**:
```json
{
  "type": "error",
  "message": "string"  // 错误信息
}
```

**SSE 格式示例**:
```
data: {"type":"error","message":"缺少必要参数: history_file 或 message"}

```

---

## REST API 接口

所有 REST API 接口的基础路径为: `/api`

### 1. 创建对话

**接口**: `POST /api/conversations`

**请求**: 无请求体

**响应**:
```json
{
  "success": true,
  "history_file": "uuid-string",
  "message": "对话创建成功"
}
```

**错误响应** (500):
```json
{
  "success": false,
  "message": "创建对话失败: 错误详情"
}
```

---

### 2. 获取对话列表

**接口**: `GET /api/conversations`

**请求**: 无参数

**响应**:
```json
{
  "success": true,
  "conversations": [
    {
      "history_file": "string",
      "last_updated": "2025-12-15 10:30:00",
      "message_count": 10
    }
  ]
}
```

**字段说明**:
- `history_file`: 对话会话ID
- `last_updated`: 最后更新时间（格式: `YYYY-MM-DD HH:MM:SS`）
- `message_count`: 消息数量

**错误响应** (500):
```json
{
  "success": false,
  "message": "获取对话列表失败: 错误详情"
}
```

---

### 3. 获取对话历史

**接口**: `GET /api/conversations/<history_file>/history`

**路径参数**:
- `history_file`: 对话会话ID

**响应**:
```json
{
  "success": true,
  "history": [
    {
      "role": "user" | "assistant",
      "content": "string"
    }
  ],
  "message_count": 10
}
```

**字段说明**:
- `history`: 对话历史记录数组
  - `role`: 消息角色（`user` 或 `assistant`）
  - `content`: 消息内容

**错误响应**:
- 404: 对话不存在
```json
{
  "success": false,
  "message": "对话 {history_file} 不存在"
}
```

- 500: 服务器错误
```json
{
  "success": false,
  "message": "获取历史对话失败: 错误详情"
}
```

---

### 4. 删除对话

**接口**: `DELETE /api/conversations/<history_file>`

**路径参数**:
- `history_file`: 对话会话ID

**响应**:
```json
{
  "success": true,
  "message": "对话删除成功"
}
```

**错误响应**:
- 404: 对话不存在
```json
{
  "success": false,
  "message": "对话 {history_file} 不存在"
}
```

- 500: 服务器错误
```json
{
  "success": false,
  "message": "删除对话失败: 错误详情"
}
```

---

### 5. 健康检查

**接口**: `GET /api/health`

**响应**:
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2025-12-15T10:30:00.123456"
}
```

---

## 数据结构说明

### ActionSpec 格式

主脑 AI 返回的标准化指令格式：

```json
{
  "actions": [
    {
      "type": "mcp" | "reply",
      "payload": "string"
    }
  ]
}
```

**字段说明**:
- `actions`: action 数组
  - `type`: 
    - `mcp`: 需要调用 MCP 工具
    - `reply`: 直接文本回复
  - `payload`: action 的具体描述（纯文本）

**示例**:
```json
{
  "actions": [
    {
      "type": "mcp",
      "payload": "从抖音平台搜索CS2饰品市场的最新走势"
    }
  ]
}
```

---

## 错误处理

### HTTP 状态码

- `200`: 成功
- `404`: 资源不存在
- `500`: 服务器内部错误

### WebSocket 错误

所有错误通过 `error` 事件发送，格式：
```json
{
  "message": "错误描述"
}
```

### 常见错误

1. **缺少参数**
   ```json
   {
     "message": "缺少必要参数: history_file 或 message"
   }
   ```

2. **对话不存在**
   ```json
   {
     "message": "对话 {history_file} 不存在"
   }
   ```

3. **处理失败**
   ```json
   {
     "message": "处理对话失败: 错误详情"
   }
   ```

---

## 示例代码

### JavaScript (EventSource / Fetch)

```javascript
// 使用 EventSource 接收 SSE 流
async function sendMessage(historyFile, message) {
  const response = await fetch('http://localhost:5001/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      history_file: historyFile,
      message: message
    })
  });

  if (!response.ok) {
    const error = await response.json();
    console.error('请求失败:', error);
    return;
  }

  // 使用 ReadableStream 读取 SSE 流
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        
        if (data.type === 'chat_callback') {
          if (data.callback_type === 'thinking') {
            console.log('AI 正在思考:', data.content);
          } else if (data.callback_type === 'reply') {
            console.log('AI 回复:', data.content);
          } else if (data.callback_type === 'error') {
            console.error('错误:', data.content);
          }
        } else if (data.type === 'response') {
          console.log('最终回复:', data.data.response);
          console.log('执行的 actions:', data.data.actions);
        } else if (data.type === 'error') {
          console.error('错误:', data.message);
        }
      }
    }
  }
}

// 使用示例
sendMessage('your-conversation-id', '你好，请帮我搜索一些信息');
```

### JavaScript (使用 EventSource - 简化版)

```javascript
// 注意：EventSource 只支持 GET 请求，所以需要先发送 POST 创建任务，然后 GET 获取流
// 或者使用上面的 Fetch API 方式

// 使用 Fetch API 是推荐方式（见上面）
```

### Python (requests)

```python
import requests
import json

# REST API: 创建对话
response = requests.post('http://localhost:5001/api/conversations')
conversation = response.json()
history_file = conversation['history_file']
print(f"创建对话: {history_file}")

# 发送消息并接收 SSE 流
def send_message(history_file, message):
    url = 'http://localhost:5001/api/chat'
    data = {
        'history_file': history_file,
        'message': message
    }
    
    response = requests.post(url, json=data, stream=True)
    
    if response.status_code != 200:
        print(f"请求失败: {response.status_code}")
        print(response.text)
        return
    
    # 读取 SSE 流
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])  # 移除 'data: ' 前缀
                    
                    if data.get('type') == 'chat_callback':
                        callback_type = data.get('callback_type')
                        content = data.get('content')
                        if callback_type == 'thinking':
                            print(f"思考: {content}")
                        elif callback_type == 'reply':
                            print(f"回复: {content}")
                        elif callback_type == 'error':
                            print(f"错误: {content}")
                    elif data.get('type') == 'response':
                        print(f"最终回复: {data['data']['response']}")
                        print(f"执行的 actions: {data['data']['actions']}")
                    elif data.get('type') == 'error':
                        print(f"错误: {data['message']}")
                except json.JSONDecodeError as e:
                    print(f"解析 JSON 失败: {e}")

# 使用示例
send_message(history_file, '你好，请帮我搜索一些信息')
```

### cURL 示例

```bash
# 创建对话
curl -X POST http://localhost:5001/api/conversations

# 发送消息（接收 SSE 流）
curl -X POST http://localhost:5001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"history_file":"your-conversation-id","message":"你好"}' \
  --no-buffer

# 获取对话列表
curl http://localhost:5001/api/conversations

# 获取对话历史
curl http://localhost:5001/api/conversations/{history_file}/history

# 删除对话
curl -X DELETE http://localhost:5001/api/conversations/{history_file}

# 健康检查
curl http://localhost:5001/api/health
```

---

## 完整流程示例

### 1. 创建对话（REST API）

```bash
POST /api/conversations
→ 返回: { "history_file": "abc-123-def" }
```

### 2. 发送消息（HTTP POST + SSE）

```javascript
const response = await fetch('http://localhost:5001/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    history_file: 'abc-123-def',
    message: '你好'
  })
});
```

### 3. 接收 SSE 流式响应

```javascript
// 读取 SSE 流
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      
      // 处理状态更新
      if (data.type === 'chat_callback') {
        if (data.callback_type === 'thinking') {
          console.log('思考:', data.content);
        } else if (data.callback_type === 'reply') {
          console.log('回复:', data.content);
        }
      }
      
      // 处理最终响应
      if (data.type === 'response') {
        console.log('最终回复:', data.data.response);
      }
    }
  }
}
```

### 4. SSE 数据流示例

```
data: {"type":"chat_callback","callback_type":"thinking","content":"正在思考.."}

data: {"type":"chat_callback","callback_type":"thinking","content":"正在搜索MCP工具"}

data: {"type":"chat_callback","callback_type":"reply","content":"这是AI的回复"}

data: {"type":"response","data":{"success":true,"response":"这是AI的回复","actions":[...]}}

```

---

## 注意事项

1. **会话隔离**: 每个 `history_file` 维护独立的 AI 实例和对话上下文
2. **SSE 流式响应**: 使用 Server-Sent Events (SSE) 推送实时状态更新，需要正确处理流式数据
3. **状态更新**: 处理过程中会发送多个 SSE 事件，需要根据 `type` 和 `callback_type` 区分处理
4. **错误处理**: 所有错误都会通过 SSE 流中的 `error` 类型事件发送，需要监听并处理
5. **超时处理**: HTTP 请求可能因网络问题超时，需要实现重试机制
6. **消息顺序**: SSE 事件按顺序到达，但需要正确解析 SSE 格式
7. **连接保持**: SSE 连接需要保持打开状态直到处理完成

---

## 更新日志

- **v2.0.0** (2025-12-15): HTTP REST API 版本
  - 移除 WebSocket，改用 HTTP REST API
  - 使用 Server-Sent Events (SSE) 推送实时状态更新
  - REST API 对话管理接口
  - 状态更新机制

- **v1.0.0** (2025-12-15): 初始版本（已废弃）
  - WebSocket 聊天接口
  - REST API 对话管理接口
  - 状态更新机制

