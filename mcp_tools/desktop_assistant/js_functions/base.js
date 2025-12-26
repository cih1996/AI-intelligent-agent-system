// 基础JS函数库
// 这些函数会被注入到JS执行环境中

// 截取指定区域屏幕并OCR识别
async function captureRegionAndOCR(x, y, width, height) {
    return await __callPythonFunction('capture_region_ocr', { x, y, width, height });
}

// 检查指定程序是否存在
function checkAppExists(appName) {
    return __callPythonFunctionSync('check_app_exists', { appName });
}

// 打开指定程序并等待弹窗
async function openAppAndWait(appName, windowTitle, timeout = 10000) {
    return await __callPythonFunction('open_app_and_wait', { 
        appName, 
        windowTitle, 
        timeout 
    });
}

// 鼠标点击
function mouseClick(x, y, button = 'left', clicks = 1) {
    return __callPythonFunctionSync('mouse_click', { x, y, button, clicks });
}

// 键盘输入文本
function keyboardType(text, interval = 0.01) {
    return __callPythonFunctionSync('keyboard_type', { text, interval });
}

// 键盘按键
function keyboardPress(key, modifiers = []) {
    return __callPythonFunctionSync('keyboard_press', { key, modifiers });
}

// 获取当前顶层窗口信息
function getTopWindow() {
    return __callPythonFunctionSync('get_top_window');
}

// 等待指定时间（毫秒）
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// 日志输出
function log(message) {
    __log(message);
}

