#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试系统工具依赖导入
用于诊断 pywin32 等模块的导入问题
"""

import sys

print("=" * 60)
print("系统工具依赖检查")
print("=" * 60)
print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.executable}")
print()

# 测试 pywin32
print("1. 检查 pywin32...")
try:
    import win32gui
    import win32con
    import win32api
    print("   ✓ win32gui 导入成功")
    print("   ✓ win32con 导入成功")
    print("   ✓ win32api 导入成功")
    print("   ✓ pywin32 可用")
except ImportError as e:
    print(f"   ✗ pywin32 导入失败: {e}")
    print("   解决方案:")
    print("   1. 确保已安装: pip install pywin32")
    print("   2. 运行 post-install 脚本: python -m pywin32_postinstall -install")
    print("   3. 如果仍有问题，尝试: python Scripts/pywin32_postinstall.py -install")
except Exception as e:
    print(f"   ✗ 其他错误: {e}")

print()

# 测试 pyautogui
print("2. 检查 pyautogui...")
try:
    import pyautogui
    print("   ✓ pyautogui 导入成功")
    print(f"   ✓ pyautogui 版本: {pyautogui.__version__}")
except ImportError as e:
    print(f"   ✗ pyautogui 导入失败: {e}")
    print("   解决方案: pip install pyautogui")
except Exception as e:
    print(f"   ✗ 其他错误: {e}")

print()

# 测试 PaddleOCR
print("3. 检查 PaddleOCR...")
try:
    from paddleocr import PaddleOCR
    print("   ✓ PaddleOCR 导入成功")
except ImportError as e:
    print(f"   ✗ PaddleOCR 导入失败: {e}")
    print("   解决方案: pip install paddleocr")
except Exception as e:
    print(f"   ✗ 其他错误: {e}")

print()

# 测试 Pillow
print("4. 检查 Pillow...")
try:
    from PIL import Image
    print("   ✓ Pillow 导入成功")
    print(f"   ✓ Pillow 版本: {Image.__version__}")
except ImportError as e:
    print(f"   ✗ Pillow 导入失败: {e}")
    print("   解决方案: pip install Pillow")
except Exception as e:
    print(f"   ✗ 其他错误: {e}")

print()
print("=" * 60)
print("检查完成")
print("=" * 60)

