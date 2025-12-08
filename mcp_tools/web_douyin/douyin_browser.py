#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
抖音网页版浏览器操作脚本
使用Selenium控制Chrome浏览器操作抖音
"""

import json
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 尝试使用webdriver-manager自动管理ChromeDriver
try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False

class DouyinBrowser:
    def __init__(self, headless=False):
        """初始化浏览器"""
        self.driver = None
        self.headless = headless
        self._is_initialized = False
    
    def _init_driver_if_needed(self):
        """按需初始化Chrome驱动（仅在需要时创建）"""
        if self._is_initialized and self.driver is not None:
            # 检查浏览器是否仍然存活
            try:
                _ = self.driver.current_window_handle
                return  # 浏览器已存在且存活
            except:
                # 浏览器已关闭，需要重新创建
                self.driver = None
                self._is_initialized = False
        
        if not self._is_initialized:
            self.init_driver()
    
    def _wait_for_page_load(self, timeout=10):
        """等待页面加载完成"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            # 额外等待一小段时间确保动态内容加载
            time.sleep(0.5)
            return True
        except TimeoutException:
            return False
    
    def _wait_for_element(self, by, value, timeout=10):
        """等待元素出现"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False
    
    def _wait_for_elements(self, by, value, timeout=10, min_count=1):
        """等待至少指定数量的元素出现"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: len(driver.find_elements(by, value)) >= min_count
            )
            return True
        except TimeoutException:
            return False
    
    def _wait_for_douyin_content(self, timeout=15):
        """等待抖音页面内容加载完成（检查视频或搜索结果）"""
        try:
            # 等待页面加载完成
            self._wait_for_page_load(timeout=5)
            
            # 尝试等待视频元素或搜索结果出现
            selectors = [
                "video",  # 视频元素
                ".search-result-card",  # 搜索结果卡片
                "div[data-e2e='video-player-digg']",  # 点赞按钮
            ]
            
            for selector in selectors:
                try:
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    time.sleep(0.5)  # 短暂等待确保内容完全渲染
                    return True
                except TimeoutException:
                    continue
            
            # 如果都没有找到，至少确保页面加载完成
            return self._wait_for_page_load(timeout=5)
        except Exception as e:
            print(f"[DEBUG] 等待抖音内容加载时出错: {e}", file=sys.stderr)
            return False
    
    def init_driver(self):
        """初始化Chrome驱动"""
        if self.driver is not None:
            return  # 已经初始化
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # 添加常用选项
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 设置用户代理
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            # 如果安装了webdriver-manager，使用它自动管理ChromeDriver
            if USE_WEBDRIVER_MANAGER:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.maximize_window()
            self._is_initialized = True
            print("浏览器已启动", file=sys.stderr)
        except Exception as e:
            print(f"启动浏览器失败: {e}", file=sys.stderr)
            if not USE_WEBDRIVER_MANAGER:
                print("提示: 安装 webdriver-manager 可以自动管理 ChromeDriver: pip install webdriver-manager", file=sys.stderr)
            raise
    
    def open_douyin(self):
        """打开抖音网页版"""
        try:
            self._init_driver_if_needed()
            current_url = self.driver.current_url if self.driver else ""
            
            # 如果已经在抖音页面，不需要重新加载
            if 'douyin.com' in current_url:
                return {"success": True, "message": "抖音网页版已打开", "reused": True}
            
            self.driver.get('https://www.douyin.com')
            self._wait_for_douyin_content()
            return {"success": True, "message": "已打开抖音网页版", "reused": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def navigate_to_url(self, url):
        """跳转到指定URL"""
        try:
            self._init_driver_if_needed()
            
            # 验证URL格式
            if not url:
                return {"success": False, "error": "URL不能为空"}
            
            # 如果URL不是以http://或https://开头，添加https://
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # 打开URL
            self.driver.get(url)
            self._wait_for_page_load()
            
            return {
                "success": True,
                "message": f"已跳转到: {url}",
                "url": self.driver.current_url,
                "title": self.driver.title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def search(self, keyword):
        """搜索指定关键词（直接打开搜索URL）"""
        try:
            self._init_driver_if_needed()
            
            # 构建搜索URL
            search_url = f"https://www.douyin.com/search/{keyword}?type=video"
            
            # 直接打开搜索页面
            self.driver.get(search_url)
            # 等待搜索结果加载
            self._wait_for_elements(By.CSS_SELECTOR, ".search-result-card", timeout=15, min_count=1)
            
            return {"success": True, "message": f"已搜索: {keyword}", "url": search_url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_search_results(self, keyword):
        """获取搜索结果列表（使用用户提供的JavaScript代码）"""
        try:
            self._init_driver_if_needed()
            
            # 构建搜索URL并打开
            search_url = f"https://www.douyin.com/search/{keyword}?type=video"
            self.driver.get(search_url)
            
            # 等待搜索结果加载
            self._wait_for_elements(By.CSS_SELECTOR, ".search-result-card", timeout=15, min_count=1)
            
            # 使用用户提供的JavaScript代码获取搜索结果
            script = """
            var cards = document.querySelectorAll(".search-result-card");
            var results = [];

            cards.forEach(function(card) {
                // 获取视频链接
                var videoLink = "";
                var aTag = card.querySelector("a[href]");
                if (aTag) {
                    videoLink = aTag.getAttribute("href") || "";
                    if (videoLink.startsWith("//")) videoLink = "https:" + videoLink;
                    else if (videoLink.startsWith("/")) videoLink = "https://www.douyin.com" + videoLink;
                }

                // 获取图片链接（优先img标签，否则取background-image）
                var imgUrl = "";
                var imgTag = card.querySelector("img");
                if (imgTag && imgTag.getAttribute("src")) {
                    imgUrl = imgTag.getAttribute("src");
                } else {
                    // 找最近的带style的div，并取 background-image
                    var divs = card.querySelectorAll("div[style]");
                    for (var i = 0; i < divs.length; i++) {
                        var style = divs[i].getAttribute("style") || "";
                        var bgMatch = style.match(/background-image:\\s*url\\(["']?(.+?)["']?\\)/);
                        if (bgMatch && bgMatch[1]) {
                            imgUrl = bgMatch[1];
                            break;
                        }
                    }
                }

                // 获取视频描述（不使用class, 一般是a下层第一个文字较多div）
                var description = "";
                var aInnerDivs = aTag ? aTag.querySelectorAll("div") : [];
                for (var i = 0; i < aInnerDivs.length; i++) {
                    var txt = aInnerDivs[i].innerText.trim();
                    // 判断是否有"#"或较长文字
                    if (txt && txt.length > 8 && txt.indexOf("#") > -1) {
                        description = txt;
                        break;
                    }
                    if (!description && txt && txt.length > 8) {
                        description = txt;
                    }
                }

                // 获取作者昵称（通常是@昵称形式，搜索span结构）
                var author = "";
                if (aTag) {
                    var spans = aTag.querySelectorAll("span");
                    for (var i = 0; i < spans.length; i++) {
                        var s = spans[i];
                        // 检查前一个节点内容为"@"
                        if (
                            s.previousSibling && 
                            s.previousSibling.textContent && 
                            s.previousSibling.textContent.trim() === '@'
                        ) {
                            author = s.innerText.trim();
                            break;
                        }
                        // 备用：找带有@的span
                        if (!author && s.innerText.trim().startsWith('@')) {
                            author = s.innerText.trim().replace(/^@+/, '');
                        }
                    }
                }

                results.push({
                    image: imgUrl,
                    video: videoLink,
                    author: author,
                    description: description
                });
            });

            return results;
            """
            
            results = self.driver.execute_script(script)
            
            if results is None:
                results = []
            
            return {
                "success": True,
                "data": {
                    "results": results,
                    "count": len(results) if results else 0
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_video_info(self):
        """获取当前视频信息（使用优化的选择器）"""
        try:
            self._init_driver_if_needed()
            
            # 确保在抖音页面
            if 'douyin.com' not in self.driver.current_url:
                self.open_douyin()
                self._wait_for_douyin_content()
            
            info = {
                "success": True,
                "data": {}
            }
            
            # 使用JavaScript获取所有信息（使用用户提供的新方法）
            script = """
                try {
                    // 当前点赞数
                    var diggs = document.querySelectorAll("div[data-e2e='video-player-digg']");
                    var digg = "";
                    if (diggs.length >= 3) {
                        digg = diggs[diggs.length-2].innerText;
                    } else if (diggs.length > 0) {
                        digg = diggs[0].innerText;
                    }

                    // 当前评论数
                    var comments = document.querySelectorAll("div[data-e2e='feed-comment-icon']");
                    var comment = "";
                    if (comments.length >= 3) {
                        comment = comments[comments.length-2].innerText;
                    } else if (comments.length > 0) {
                        comment = comments[0].innerText;
                    }

                    // 博主名称
                    var names = document.querySelectorAll(".account-name-text");
                    var name = "";
                    if (names.length >= 3) {
                        name = names[names.length-2].innerText;
                    } else if (names.length > 0) {
                        name = names[0].innerText;
                    }

                    // 发布时间
                    var times = document.querySelectorAll(".video-create-time");
                    var timestr = "";
                    if (times.length >= 3) {
                        timestr = times[times.length-2].innerText;
                    } else if (times.length > 0) {
                        timestr = times[0].innerText;
                    }

                    // 视频描述
                    var descs = document.querySelectorAll("div[data-e2e='video-desc']");
                    var desc = "";
                    if (descs.length >= 3) {
                        desc = descs[descs.length-2].innerText;
                    } else if (descs.length > 0) {
                        desc = descs[0].innerText;
                    }

                    // 播放进度百分比
                    var progresss = document.querySelectorAll(".xgplayer-progress-btn");
                    var progress = "";
                    if (progresss.length >= 3) {
                        progress = progresss[progresss.length-2].style.left;
                    } else if (progresss.length > 0) {
                        progress = progresss[0].style.left;
                    }

                    // 播放时长
                    var durations = document.querySelectorAll(".time-duration");
                    var duration = "";
                    if (durations.length >= 3) {
                        duration = durations[durations.length-2].innerText;
                    } else if (durations.length > 0) {
                        duration = durations[0].innerText;
                    }

                    // 当前播放时间
                    var currents = document.querySelectorAll(".time-current");
                    var current = "";
                    if (currents.length >= 3) {
                        current = currents[currents.length-2].innerText;
                    } else if (currents.length > 0) {
                        current = currents[0].innerText;
                    }

                    // 获取视频元素信息
                    var videos = document.querySelectorAll("video");
                    var videoInfo = {};
                    if (videos.length > 0) {
                        var video = videos[0];
                        videoInfo.videoCurrentTime = video.currentTime;
                        videoInfo.videoDuration = video.duration;
                        videoInfo.videoPaused = video.paused;
                        videoInfo.videoVolume = video.volume;
                        videoInfo.videoPlaybackRate = video.playbackRate;
                    }

                    return {
                        digg: digg,
                        comment: comment,
                        name: name,
                        timestr: timestr,
                        desc: desc,
                        progress: progress,
                        duration: duration,
                        current: current,
                        videoInfo: videoInfo
                    };
                } catch (e) {
                    return {
                        error: e.toString(),
                        message: e.message,
                        stack: e.stack
                    };
                }
            ;
            """
            
            video_data = self.driver.execute_script(script)
         
            
            # 检查返回数据是否有效（None或不是字典）
            if video_data is None:
                # 尝试获取更多调试信息
                debug_info = self.driver.execute_script("""
                    return {
                        url: window.location.href,
                        diggsCount: document.querySelectorAll("div[data-e2e='video-player-digg']").length,
                        commentsCount: document.querySelectorAll("div[data-e2e='feed-comment-icon']").length,
                        namesCount: document.querySelectorAll(".account-name-text").length,
                        videosCount: document.querySelectorAll("video").length
                    };
                """)
                return {
                    "success": False, 
                    "error": f"无法获取视频信息，返回数据为None。调试信息: {json.dumps(debug_info, ensure_ascii=False)}"
                }
            
            # 检查是否有JavaScript执行错误
            if isinstance(video_data, dict) and 'error' in video_data:
                return {
                    "success": False, 
                    "error": f"JavaScript执行错误: {video_data.get('message', video_data.get('error', '未知错误'))}",
                    "stack": video_data.get('stack', '')
                }
            
            # 确保video_data是字典类型
            if not isinstance(video_data, dict):
                return {
                    "success": False,
                    "error": f"返回数据类型错误: {type(video_data)}, 值: {video_data}"
                }
            
            # 即使所有字段都是空字符串，也应该返回数据（用于调试）
            print(f"[DEBUG] video_data keys: {list(video_data.keys()) if isinstance(video_data, dict) else 'N/A'}", file=sys.stderr)
            
            # 处理点赞数（转换为数字）
            if video_data.get('digg'):
                digg_text = video_data.get('digg', '')
                like_count = self._parse_number(digg_text)
                if like_count is not None:
                    info["data"]["likeCount"] = like_count
                info["data"]["likeCountText"] = digg_text
            
            # 处理评论数（转换为数字）
            if video_data.get('comment'):
                comment_text = video_data.get('comment', '')
                comment_count = self._parse_number(comment_text)
                if comment_count is not None:
                    info["data"]["commentCount"] = comment_count
                info["data"]["commentCountText"] = comment_text
            
            # 博主名称
            if video_data.get('name'):
                info["data"]["authorName"] = video_data['name']
            
            # 发布时间
            if video_data.get('timestr'):
                info["data"]["publishTime"] = video_data['timestr']
            
            # 视频描述
            if video_data.get('desc'):
                info["data"]["description"] = video_data['desc']
            
            # 播放进度百分比
            if video_data.get('progress'):
                info["data"]["progressPercent"] = video_data['progress']
            
            # 播放时长
            if video_data.get('duration'):
                info["data"]["durationText"] = video_data['duration']
            
            # 当前播放时间
            if video_data.get('current'):
                info["data"]["currentTimeText"] = video_data['current']
            
            # 视频元素信息
            video_info = video_data.get('videoInfo')
            if video_info and isinstance(video_info, dict):
                if video_info.get('videoCurrentTime') is not None:
                    info["data"]["videoCurrentTime"] = video_info['videoCurrentTime']
                
                if video_info.get('videoDuration') is not None:
                    info["data"]["videoDuration"] = video_info['videoDuration']
                
                if video_info.get('videoPaused') is not None:
                    info["data"]["videoPaused"] = video_info['videoPaused']
                
                if video_info.get('videoVolume') is not None:
                    info["data"]["videoVolume"] = video_info['videoVolume']
                
                if video_info.get('videoPlaybackRate') is not None:
                    info["data"]["videoPlaybackRate"] = video_info['videoPlaybackRate']
            
            return info
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_number(self, text):
        """从文本中解析数字（支持中文格式如1.2万）"""
        if not text:
            return None
        
        import re
        
        # 处理"万"单位
        wan_match = re.search(r'([\d.]+)万', text)
        if wan_match:
            return int(float(wan_match.group(1)) * 10000)
        
        # 处理"亿"单位
        yi_match = re.search(r'([\d.]+)亿', text)
        if yi_match:
            return int(float(yi_match.group(1)) * 100000000)
        
        # 提取普通数字
        num_match = re.search(r'[\d,]+', text.replace(',', ''))
        if num_match:
            try:
                return int(num_match.group(0))
            except:
                pass
        
        return None
    
    def scroll(self, direction='next'):
        """滚动到下一个/上一个视频"""
        try:
            self._init_driver_if_needed()
            
            # 使用抖音官方的视频切换按钮
            if direction == 'next':
                script = "document.querySelector(\"div[data-e2e='video-switch-next-arrow']\").click();"
                message = "已切换到下一条视频"
            else:
                script = "document.querySelector(\"div[data-e2e='video-switch-prev-arrow']\").click();"
                message = "已切换到上一条视频"
            
            self.driver.execute_script(script)
            # 等待新视频加载
            self._wait_for_elements(By.CSS_SELECTOR, "video", timeout=10, min_count=1)
            # 额外等待视频信息元素出现
            self._wait_for_elements(By.CSS_SELECTOR, "div[data-e2e='video-player-digg']", timeout=5, min_count=1)
            
            return {"success": True, "message": message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def like(self):
        """点赞当前视频"""
        try:
            self._init_driver_if_needed()
            
            like_selectors = [
                "button[class*='like']",
                "[class*='like'][role='button']",
                "[aria-label*='点赞']"
            ]
            
            for selector in like_selectors:
                try:
                    like_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    like_button.click()
                    # 短暂等待确保操作完成
                    time.sleep(0.3)
                    return {"success": True, "message": "已点赞"}
                except TimeoutException:
                    continue
            
            return {"success": False, "error": "未找到点赞按钮"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_page_info(self):
        """获取页面信息"""
        try:
            self._init_driver_if_needed()
            
            return {
                "success": True,
                "data": {
                    "url": self.driver.current_url,
                    "title": self.driver.title,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def toggle_comments(self):
        """打开/关闭评论区（严格按照用户提供的逻辑）"""
        try:
            self._init_driver_if_needed()
            
            script = """
                var commentBtns = document.querySelectorAll("div[data-e2e='feed-comment-icon']");
                if(commentBtns.length >= 3){
                    commentBtns[commentBtns.length - 2].click();
                } else {
                    commentBtns[0].click();
                }
                return {success: true};
            """
            
            result = self.driver.execute_script(script)
            # 等待评论区加载/关闭（如果打开评论区，等待评论元素出现）
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "div[data-e2e='comment-item']")) > 0 or 
                                   len(driver.find_elements(By.CSS_SELECTOR, "div[data-e2e='feed-comment-icon']")) > 0
                )
            except TimeoutException:
                pass  # 如果超时，可能是关闭评论区，继续执行
            
            if result and result.get('success'):
                return {"success": True, "message": "已切换评论区状态"}
            else:
                return {"success": False, "error": "未找到评论按钮"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_comments_list(self):
        """获取评论区列表"""
        try:
            self._init_driver_if_needed()
            
            script = """
          
                var comments = document.querySelectorAll("div[data-e2e='comment-item']");
                var commentList = [];
                
                comments.forEach(function(comment) {
                    // 找到回复按钮
                    let replyBtn = null;
                    let replyBtnCandidates = comment.querySelectorAll("[data-popupid]");
                    for (let btn of replyBtnCandidates) {
                        let span = btn.querySelector("span");
                        if (span && span.textContent.trim() === "回复") {
                            replyBtn = btn;
                            break;
                        }
                    }
                    
                    // 获取昵称
                    let nickname = '';
                    let infoWrap = comment.querySelector('.comment-item-info-wrap');
                    if (infoWrap) {
                        nickname = infoWrap.innerText.trim();
                    }
                    
                    // 获取评论内容
                    let commentContent = '';
                    if (infoWrap && infoWrap.nextElementSibling) {
                        commentContent = infoWrap.nextElementSibling.innerText.trim();
                    }
                    
                    commentList.push({
                        nickname: nickname,
                        content: commentContent,
                        hasReplyBtn: replyBtn !== null
                    });
                });
                
                return commentList;
           
            """
            
            comments_list = self.driver.execute_script(script)
            
            return {
                "success": True,
                "data": {
                    "comments": comments_list,
                    "count": len(comments_list) if comments_list else 0
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()

# 全局浏览器实例
_browser = None

def get_browser():
    """获取或创建浏览器实例"""
    global _browser
    if _browser is None:
        _browser = DouyinBrowser(headless=False)
        _browser.open_douyin()
    return _browser

def main():
    """主函数 - 处理命令行调用"""
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "缺少参数"}))
        return
    
    action = sys.argv[1]
    browser = get_browser()
    
    try:
        if action == 'search':
            keyword = sys.argv[2] if len(sys.argv) > 2 else ""
            result = browser.search(keyword)
        elif action == 'getVideoInfo':
            result = browser.get_video_info()
        elif action == 'scroll':
            direction = sys.argv[2] if len(sys.argv) > 2 else 'next'
            result = browser.scroll(direction)
        elif action == 'like':
            result = browser.like()
        elif action == 'getPageInfo':
            result = browser.get_page_info()
        elif action == 'open':
            result = browser.open_douyin()
        else:
            result = {"success": False, "error": f"未知操作: {action}"}
        
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))

if __name__ == '__main__':
    main()

