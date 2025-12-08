#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
抖音网页版浏览器HTTP服务器
保持浏览器实例持续运行，通过HTTP API提供服务
"""

import json
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from douyin_browser import DouyinBrowser

# 全局浏览器实例
_browser = None
_browser_lock = threading.Lock()

def get_browser():
    """获取或创建浏览器实例（支持持久化）"""
    global _browser
    with _browser_lock:
        if _browser is None:
            _browser = DouyinBrowser(headless=False)
        elif not _is_browser_alive(_browser):
            # 浏览器已关闭，重新创建
            try:
                _browser.close()
            except:
                pass
            _browser = DouyinBrowser(headless=False)
        return _browser

def _is_browser_alive(browser):
    """检查浏览器是否仍然存活"""
    if browser is None or browser.driver is None:
        return False
    try:
        _ = browser.driver.current_window_handle
        return True
    except:
        return False

class DouyinHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        try:
            if path == '/health':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "browser": "running" if _browser is not None else "not started"
                }, ensure_ascii=False).encode('utf-8'))
                return
            
            elif path == '/open':
                browser = get_browser()
                # 检查是否已经在抖音页面
                try:
                    current_url = browser.driver.current_url if browser.driver else ""
                    if 'douyin.com' in current_url:
                        result = {"success": True, "message": "抖音网页版已打开", "reused": True}
                    else:
                        result = browser.open_douyin()
                except:
                    result = browser.open_douyin()
                self._send_json_response(result)
                return
            
            elif path == '/search':
                keyword = query_params.get('keyword', [''])[0]
                if not keyword:
                    self._send_error_response(400, "缺少keyword参数")
                    return
                
                browser = get_browser()
                result = browser.search(keyword)
                self._send_json_response(result)
                return
            
            elif path == '/getVideoInfo':
                browser = get_browser()
                result = browser.get_video_info()
                self._send_json_response(result)
                return
            
            elif path == '/scroll':
                direction = query_params.get('direction', ['next'])[0]
                browser = get_browser()
                result = browser.scroll(direction)
                self._send_json_response(result)
                return
            
            elif path == '/like':
                browser = get_browser()
                result = browser.like()
                self._send_json_response(result)
                return
            
            elif path == '/getPageInfo':
                browser = get_browser()
                result = browser.get_page_info()
                self._send_json_response(result)
                return
            
            elif path == '/close':
                global _browser
                with _browser_lock:
                    if _browser:
                        _browser.close()
                        _browser = None
                self._send_json_response({"success": True, "message": "浏览器已关闭"})
                return
            
            else:
                self._send_error_response(404, f"未知路径: {path}")
                return
                
        except Exception as e:
            self._send_error_response(500, str(e))
    
    def do_POST(self):
        """处理POST请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode('utf-8'))
                except:
                    data = {}
            else:
                data = {}
            
            if path == '/search':
                keyword = data.get('keyword', '')
                if not keyword:
                    self._send_error_response(400, "缺少keyword参数")
                    return
                
                browser = get_browser()
                result = browser.search(keyword)
                self._send_json_response(result)
                return
            
            elif path == '/scroll':
                direction = data.get('direction', 'next')
                browser = get_browser()
                result = browser.scroll(direction)
                self._send_json_response(result)
                return
            
            else:
                self._send_error_response(404, f"未知路径: {path}")
                return
                
        except Exception as e:
            self._send_error_response(500, str(e))
    
    def _send_json_response(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = json.dumps(data, ensure_ascii=False)
        self.wfile.write(response.encode('utf-8'))
    
    def _send_error_response(self, status_code, message):
        """发送错误响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_response = json.dumps({
            "success": False,
            "error": message
        }, ensure_ascii=False)
        self.wfile.write(error_response.encode('utf-8'))
    
    def log_message(self, format, *args):
        """重写日志方法，输出到stderr"""
        import sys
        message = format % args
        print(f"[HTTP Server] {message}", file=sys.stderr)

def run_server(port=8765):
    """运行HTTP服务器"""
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, DouyinHandler)
    print(f"抖音浏览器HTTP服务器已启动，监听端口 {port}", file=sys.stderr)
    print(f"访问 http://localhost:{port}/health 检查服务状态", file=sys.stderr)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...", file=sys.stderr)
        global _browser
        with _browser_lock:
            if _browser:
                _browser.close()
                _browser = None
        httpd.shutdown()
        print("服务器已关闭", file=sys.stderr)

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    run_server(port)

