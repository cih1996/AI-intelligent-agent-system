#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
截图功能模块
支持全屏截图和智能差异截图
"""

import os
import time
from pathlib import Path
from typing import Optional, Tuple
import hashlib

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[Screenshot] 警告: pyautogui 未安装，截图功能将不可用")

try:
    from PIL import Image, ImageChops
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[Screenshot] 警告: Pillow 未安装，智能截图功能将不可用")


class ScreenshotManager:
    """截图管理器，支持智能差异截图"""
    
    def __init__(self, temp_dir: Path):
        """
        初始化截图管理器
        
        Args:
            temp_dir: 临时文件目录
        """
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存上一次的截图用于差异比较
        self.last_screenshot_path: Optional[Path] = None
        self.last_screenshot_hash: Optional[str] = None
    
    def capture_screen(self, output_path: Optional[Path] = None, scale_factor: float = 0.5) -> Path:
        """
        截取当前屏幕
        
        Args:
            output_path: 输出路径，如果为None则自动生成
            scale_factor: 缩放因子，用于减小图片尺寸（0.5表示缩小到50%）
            
        Returns:
            截图文件路径
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui 未安装，无法截图")
        
        # 截取全屏
        screenshot = pyautogui.screenshot()
        
        # 缩放图片以减小token消耗
        if PIL_AVAILABLE and scale_factor < 1.0:
            width, height = screenshot.size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 生成输出路径
        if output_path is None:
            timestamp = int(time.time() * 1000)
            output_path = self.temp_dir / f"screenshot_{timestamp}.png"
        
        # 保存截图
        screenshot.save(output_path)
        
        print(f"[Screenshot] 截图已保存: {output_path} ({output_path.stat().st_size} bytes)")
        
        return output_path
    
    def capture_region(self, x: int, y: int, width: int, height: int, 
                      output_path: Optional[Path] = None) -> Path:
        """
        截取指定区域
        
        Args:
            x: 左上角X坐标
            y: 左上角Y坐标
            width: 宽度
            height: 高度
            output_path: 输出路径
            
        Returns:
            截图文件路径
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui 未安装，无法截图")
        
        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        
        if output_path is None:
            timestamp = int(time.time() * 1000)
            output_path = self.temp_dir / f"region_{timestamp}.png"
        
        screenshot.save(output_path)
        
        print(f"[Screenshot] 区域截图已保存: {output_path}")
        
        return output_path
    
    def capture_changes(self, output_path: Optional[Path] = None, 
                       threshold: int = 10) -> Optional[Path]:
        """
        智能截图：只截取与上次截图不同的区域
        
        Args:
            output_path: 输出路径
            threshold: 差异阈值（像素值差异）
            
        Returns:
            截图文件路径，如果无变化则返回None
        """
        if not PIL_AVAILABLE or not PYAUTOGUI_AVAILABLE:
            # 如果不支持智能截图，直接返回全屏截图
            return self.capture_screen(output_path)
        
        # 截取当前屏幕
        current_screenshot = pyautogui.screenshot()
        
        # 计算当前截图的哈希值
        current_hash = self._calculate_image_hash(current_screenshot)
        
        # 如果与上次相同，返回None
        if self.last_screenshot_hash == current_hash:
            print("[Screenshot] 屏幕无变化，跳过截图")
            return None
        
        # 如果有上次截图，计算差异
        if self.last_screenshot_path and self.last_screenshot_path.exists():
            try:
                last_image = Image.open(self.last_screenshot_path)
                current_image = current_screenshot
                
                # 确保尺寸相同
                if last_image.size != current_image.size:
                    current_image = current_image.resize(last_image.size, Image.Resampling.LANCZOS)
                
                # 计算差异
                diff = ImageChops.difference(last_image, current_image)
                
                # 获取差异区域边界
                bbox = diff.getbbox()
                
                if bbox:
                    # 有差异，截取差异区域
                    x1, y1, x2, y2 = bbox
                    # 添加一些边距
                    margin = 20
                    x1 = max(0, x1 - margin)
                    y1 = max(0, y1 - margin)
                    x2 = min(current_image.width, x2 + margin)
                    y2 = min(current_image.height, y2 + margin)
                    
                    # 截取差异区域
                    changed_region = current_image.crop((x1, y1, x2, y2))
                    
                    # 生成输出路径
                    if output_path is None:
                        timestamp = int(time.time() * 1000)
                        output_path = self.temp_dir / f"change_{timestamp}.png"
                    
                    changed_region.save(output_path)
                    
                    print(f"[Screenshot] 差异截图已保存: {output_path} (区域: {x1},{y1} - {x2},{y2})")
                    
                    # 更新上次截图
                    self.last_screenshot_path = self.temp_dir / f"last_full_{timestamp}.png"
                    current_image.save(self.last_screenshot_path)
                    self.last_screenshot_hash = current_hash
                    
                    return output_path
                else:
                    # 无差异
                    print("[Screenshot] 屏幕无变化")
                    self.last_screenshot_hash = current_hash
                    return None
                    
            except Exception as e:
                print(f"[Screenshot] 计算差异失败: {str(e)}，使用全屏截图")
                # 失败时使用全屏截图
                return self.capture_screen(output_path)
        else:
            # 第一次截图，保存全屏
            if output_path is None:
                timestamp = int(time.time() * 1000)
                output_path = self.temp_dir / f"change_{timestamp}.png"
            
            current_screenshot.save(output_path)
            
            # 保存为上次截图
            self.last_screenshot_path = self.temp_dir / f"last_full_{int(time.time() * 1000)}.png"
            current_screenshot.save(self.last_screenshot_path)
            self.last_screenshot_hash = current_hash
            
            print(f"[Screenshot] 首次截图已保存: {output_path}")
            
            return output_path
    
    def _calculate_image_hash(self, image) -> str:
        """计算图片的哈希值"""
        if isinstance(image, Image.Image):
            # 转换为numpy数组计算哈希
            import numpy as np
            img_array = np.array(image)
            img_bytes = img_array.tobytes()
        else:
            img_bytes = image.tobytes()
        
        return hashlib.md5(img_bytes).hexdigest()
    
    def reset(self):
        """重置截图管理器，清空上次截图记录"""
        self.last_screenshot_path = None
        self.last_screenshot_hash = None
        print("[Screenshot] 截图管理器已重置")

