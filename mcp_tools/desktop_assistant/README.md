# Desktop Assistant MCP Tool

桌面操作助手 MCP 工具，基于 GPT-4o 和 JS 脚本执行引擎。

## 功能特性

- 基于 GPT-4o 的智能桌面操作
- JS 脚本执行引擎
- 智能截图（只截取变化区域）
- 系统信息获取（已安装应用、打开窗口）
- OCR 文字识别
- 鼠标键盘操作

## 环境要求

### Python 依赖

```bash
pip install pyautogui pywin32 pillow paddleocr requests
```

### Node.js

需要安装 Node.js（用于执行 JS 脚本）

### 配置文件

在 `desktop_assistant` 目录下创建 `.env` 文件：

```env
# OpenAI API 配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
DESKTOP_ASSISTANT_MODEL=gpt-4o

# 代理配置（如果需要）
USE_PROXY=false
PROXY_URL=http://127.0.0.1:7890
```

**注意**：请将 `your_openai_api_key_here` 替换为你的实际 API Key。

配置项说明：
- `OPENAI_API_KEY`: OpenAI API Key（必需）
- `OPENAI_BASE_URL`: API 基础 URL（可选，默认 https://api.openai.com/v1）
- `DESKTOP_ASSISTANT_MODEL`: 使用的模型（可选，默认 gpt-4o）
- `USE_PROXY`: 是否使用代理（可选，默认 false）
- `PROXY_URL`: 代理 URL（可选）

## 使用方法

### MCP 工具调用

```json
{
  "name": "desktop_assistant.chat",
  "arguments": {
    "instruction": "打开抖音搜索 CS2市场"
  }
}
```

## 工作流程

1. 获取系统信息（已安装应用、打开窗口）
2. 截取当前屏幕（等比缩小）
3. 将需求、截屏、系统信息提交给 GPT-4o
4. GPT-4o 生成 JS 脚本代码
5. 执行 JS 代码并记录日志
6. 智能截图（只截取变化部分）回传 GPT-4o
7. 根据 GPT-4o 判断继续执行或返回结果

## JS 函数库

JS 脚本可以使用以下函数：

- `captureRegionAndOCR(x, y, width, height)`: 截取区域并OCR
- `checkAppExists(appName)`: 检查应用是否存在
- `openAppAndWait(appName, windowTitle, timeout)`: 打开应用并等待
- `mouseClick(x, y, button, clicks)`: 鼠标点击
- `keyboardType(text, interval)`: 键盘输入
- `keyboardPress(key, modifiers)`: 键盘按键
- `getTopWindow()`: 获取顶层窗口信息
- `sleep(ms)`: 等待
- `log(message)`: 日志输出

## 目录结构

```
desktop_assistant/
├── server.py              # 主服务器
├── manifest.json          # MCP 清单
├── tool.json              # 工具定义
├── core/                  # 核心模块
│   ├── gpt_client.py     # GPT 客户端
│   ├── system_info.py    # 系统信息获取
│   ├── screenshot.py     # 截图功能
│   └── js_executor.py    # JS 执行引擎
├── js_functions/          # JS 函数库
│   └── base.js           # 基础函数
└── prompts/               # 提示词
    └── system_prompt.txt  # 系统提示词
```

## 注意事项

1. JS 执行引擎需要 Node.js 支持
2. OCR 功能需要 PaddleOCR
3. 窗口操作需要 pywin32
4. 鼠标键盘操作需要 pyautogui
5. 首次运行可能需要下载 OCR 模型

