"""
图片格式转换工具类
使用ffmpeg将各种图片格式转换为PNG
"""

import os
import subprocess
import tempfile
from pathlib import Path


class ImageConverter:
    """图片格式转换工具类"""
    
    # 支持的图片格式
    SUPPORTED_FORMATS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', 
        '.tiff', '.tif', '.webp', '.ico', '.ppm',
        '.pgm', '.pbm', '.pnm', '.pcx', '.dds',
        '.tga', '.sgi', '.rgb', '.bw'
    }
    
    @staticmethod
    def is_supported_format(file_path):
        """
        检查文件是否是支持的图片格式
        :param file_path: 文件路径
        :return: bool
        """
        ext = Path(file_path).suffix.lower()
        return ext in ImageConverter.SUPPORTED_FORMATS
    
    @staticmethod
    def convert_to_png(image_path, output_path=None, keep_original=True, quality=95):
        """
        使用ffmpeg将图片转换为PNG格式
        :param image_path: 输入图片路径
        :param output_path: 输出路径，如果为None则在临时目录生成
        :param keep_original: 是否保留原文件（仅当output_path为None时有效）
        :param quality: 压缩质量(1-100)，对PNG影响不大
        :return: dict包含success, message, output_path等信息
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "message": f"文件不存在: {image_path}",
                    "output_path": None
                }
            
            # 检查文件大小
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                return {
                    "success": False,
                    "message": f"文件为空: {image_path}",
                    "output_path": None
                }
            
            # 确定输出路径
            if output_path is None:
                # 如果原文件已经是PNG，且要求保留原文件
                if Path(image_path).suffix.lower() == '.png':
                    return {
                        "success": True,
                        "message": "文件已经是PNG格式",
                        "output_path": image_path,
                        "is_original": True
                    }
                
                # 生成新的文件名
                original_name = Path(image_path).stem
                if keep_original:
                    # 在同目录下创建新文件
                    output_dir = Path(image_path).parent
                    output_path = output_dir / f"{original_name}_converted.png"
                else:
                    # 在临时目录创建
                    temp_dir = tempfile.gettempdir()
                    output_path = Path(temp_dir) / f"{original_name}.png"
            else:
                output_path = Path(output_path)
                # 确保输出目录存在
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用ffmpeg进行转换
            # -y: 覆盖输出文件
            # -i: 输入文件
            # -frames:v 1: 只处理第一帧（对于动图）
            # -compression_level: PNG压缩级别（0-100）
            compression = 100 - quality if quality < 100 else 0
            
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出文件
                '-i', str(image_path),  # 输入文件
                '-frames:v', '1',  # 只处理第一帧
                '-compression_level', str(compression),  # 压缩级别
                str(output_path)  # 输出文件
            ]
            
            # 执行ffmpeg命令
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0  # Windows下隐藏窗口
            )
            
            # 检查是否成功
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                return {
                    "success": False,
                    "message": f"ffmpeg转换失败: {error_msg[:200]}",
                    "output_path": None,
                    "error_detail": error_msg
                }
            
            # 验证输出文件是否存在
            if not os.path.exists(output_path):
                return {
                    "success": False,
                    "message": "转换完成但输出文件不存在",
                    "output_path": None
                }
            
            # 获取文件大小信息
            original_size = os.path.getsize(image_path)
            new_size = os.path.getsize(output_path)
            size_reduction = ((original_size - new_size) / original_size * 100) if original_size > new_size else 0
            
            return {
                "success": True,
                "message": "转换成功",
                "output_path": str(output_path),
                "original_path": image_path,
                "original_size": original_size,
                "new_size": new_size,
                "size_reduction_percent": round(size_reduction, 2),
                "is_original": False
            }
                
        except FileNotFoundError:
            return {
                "success": False,
                "message": "未找到ffmpeg，请确保已安装ffmpeg并添加到系统PATH",
                "output_path": None,
                "error": "ffmpeg not found"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"转换失败: {str(e)}",
                "output_path": None,
                "error": str(e)
            }
    
    @staticmethod
    def convert_to_png_simple(image_path):
        """
        简化版本：将图片转换为PNG格式，返回转换后的路径
        如果已经是PNG格式，直接返回原路径
        :param image_path: 输入图片路径
        :return: str 转换后的PNG文件路径，如果失败则返回None
        """
        result = ImageConverter.convert_to_png(image_path)
        if result["success"]:
            return result["output_path"]
        else:
            print(f"转换失败: {result['message']}")
            return None
    
    @staticmethod
    def batch_convert_to_png(image_paths, output_dir=None, keep_original=True):
        """
        批量转换图片为PNG格式
        :param image_paths: 图片路径列表
        :param output_dir: 输出目录
        :param keep_original: 是否保留原文件
        :return: dict包含成功和失败的结果
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(image_paths),
            "success_count": 0,
            "failed_count": 0
        }
        
        for image_path in image_paths:
            # 如果指定了输出目录，生成输出路径
            if output_dir:
                output_path = Path(output_dir) / f"{Path(image_path).stem}.png"
            else:
                output_path = None
            
            result = ImageConverter.convert_to_png(
                image_path, 
                output_path=output_path,
                keep_original=keep_original
            )
            
            if result["success"]:
                results["success"].append(result)
                results["success_count"] += 1
            else:
                results["failed"].append({
                    "path": image_path,
                    "error": result["message"]
                })
                results["failed_count"] += 1
        
        return results


# 便捷函数
def convert_image_to_png(image_path, output_path=None):
    """
    便捷函数：将图片转换为PNG格式
    :param image_path: 输入图片路径
    :param output_path: 输出路径（可选）
    :return: 转换后的PNG文件路径，失败返回None
    """
    return ImageConverter.convert_to_png_simple(image_path)
