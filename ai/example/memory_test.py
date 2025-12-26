#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆管理AI测试脚本
测试3个记忆管理AI的工作流程：
1. MemoryManagerAgent - 记忆大纲选择AI
2. MemoryRouterAgent - 记忆路由选择AI
3. MemoryShardsAgent - 记忆碎片增删改检测AI
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.agents.memory_manager_agent import MemoryManagerAgent
from services.agents.memory_router_agent import MemoryRouterAgent
from services.agents.memory_shards_agent import MemoryShardsAgent


def setup_test_memory_files(history_file: str = "test_user"):
    """
    创建测试用的记忆文件
    """
    memory_dir = Path(".memory") / history_file
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建 desktop_sop.json
    desktop_sop_data = [
        {
            "key": "mem_001",
            "category": "desktop_sop",
            "shared": {
                "payload": {
                    "custom_data": {
                        "steps": ["打开IDE", "创建文件", "编写代码"],
                        "notes": "标准开发流程"
                    }
                }
            },
            "importance": 8,
            "source": "用户输入",
            "tags": ["流程", "开发"],
            "trigger_count": 5,
            "created_at": "2024-12-01T10:00:00",
            "updated_at": "2024-12-10T10:00:00",
            "last_triggered": "2024-12-10T10:00:00"
        }
    ]
    
    # 创建 user_preferences.json
    user_preferences_data = [
        {
            "key": "mem_002",
            "category": "user_preferences",
            "shared": {
                "payload": {
                    "custom_data": {
                        "theme": "dark",
                        "language": "zh-CN",
                        "editor": "vscode"
                    }
                }
            },
            "importance": 9,
            "source": "用户输入",
            "tags": ["偏好", "设置"],
            "trigger_count": 10,
            "created_at": "2024-12-01T10:00:00",
            "updated_at": "2024-12-10T10:00:00",
            "last_triggered": "2024-12-10T10:00:00"
        }
    ]
    
    # 创建 coding_style.json
    coding_style_data = [
        {
            "key": "mem_003",
            "category": "coding_style",
            "shared": {
                "payload": {
                    "custom_data": {
                        "language": "python",
                        "style": "pep8",
                        "max_line_length": 120,
                        "indent": "spaces"
                    }
                }
            },
            "importance": 7,
            "source": "用户输入",
            "tags": ["编码", "规范"],
            "trigger_count": 8,
            "created_at": "2024-12-01T10:00:00",
            "updated_at": "2024-12-10T10:00:00",
            "last_triggered": "2024-12-10T10:00:00"
        }
    ]
    
    # 写入文件
    with open(memory_dir / "desktop_sop.json", 'w', encoding='utf-8') as f:
        json.dump(desktop_sop_data, f, ensure_ascii=False, indent=2)
    
    with open(memory_dir / "user_preferences.json", 'w', encoding='utf-8') as f:
        json.dump(user_preferences_data, f, ensure_ascii=False, indent=2)
    
    with open(memory_dir / "coding_style.json", 'w', encoding='utf-8') as f:
        json.dump(coding_style_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 测试记忆文件已创建在: {memory_dir}")
    print(f"  - desktop_sop.json")
    print(f"  - user_preferences.json")
    print(f"  - coding_style.json")


def main():
    """
    测试完整工作流程
    """
    print("\n" + "="*60)
    print("完整工作流程测试")
    print("="*60)
    
    # 初始化所有AI
    manager = MemoryManagerAgent(provider='deepseek', history_file='test_user')
    router = MemoryRouterAgent(provider='deepseek', history_file='test_user')
    shards = MemoryShardsAgent(provider='deepseek', history_file='test_user')
    

    user_description = "按照我的编码风格创建一个新的功能模块"

    # 步骤1: 选择相关的大纲
    print("\n步骤1: 记忆大纲选择AI选择相关大纲...")
    selected_outlines = manager.select_outlines(user_description, "执行AI")
    print(f"✓ 选择的大纲: {selected_outlines}")
    
    if not selected_outlines:
        print("⚠ 未选择任何大纲，跳过后续步骤")
        return
    
    # 步骤2: 从选定大纲中选择payload路径
    print("\n步骤2: 记忆路由选择AI选择payload路径...")
    payload_paths = router.select_payload_paths(selected_outlines, "执行AI")
    print(f"✓ 选择的payload路径: {payload_paths}")
    
    # 步骤3: 根据路径获取实际的payload数据（用于注入到下一层AI）
    print("\n步骤3: 根据路径获取payload数据...")
    for path in payload_paths:
        payload = router.get_payload_by_path(path)
        if payload:
            print(f"✓ 路径: {path}")
            print(f"  数据: {router.payload_to_markdown(payload)}")

    # 步骤4: 检测记忆变更（模拟对话后的记忆更新）
    print("\n步骤4: 记忆碎片增删改检测AI检测记忆变更...")
    user_input = "我创建了一个新的用户管理模块，使用了Python和PEP8规范"
    ai_output = "好的，我已经按照你的编码风格创建了用户管理模块。"
    
    changes = shards.detect_memory_changes(
        user_input=user_input,
        ai_output=ai_output
    )
    
    print(f"✓ 检测到的变更操作数量: {len(changes)}")
    if changes:
        print("\n步骤5: 应用变更操作到记忆文件...")
        stats = shards.apply_memory_changes(changes)
        print(f"✓ 应用完成: 新增={stats['added']}, 更新={stats['updated']}, 删除={stats['deleted']}")


if __name__ == "__main__":
    main()

