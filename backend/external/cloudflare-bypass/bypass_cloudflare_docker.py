#!/usr/bin/env python3
"""
Cloudflare 绕过工具 - Docker 版本
基于 bypass_cloudflare_v5.py，优化用于 Docker 容器运行

核心功能：
- 支持 --output-json 参数，输出纯 JSON 格式结果
- 适配 Xvfb 虚拟显示环境
- 验证成功后输出 cookies 和 headers 供后续使用
"""

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# PyAutoGUI 用于模拟真实鼠标操作
PYAUTOGUI_AVAILABLE = False
PYAUTOGUI_ERROR = None
try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
    pyautogui.PAUSE = 0.1
    pyautogui.FAILSAFE = False
except Exception as e:
    PYAUTOGUI_AVAILABLE = False
    PYAUTOGUI_ERROR = str(e)


# ============================================================
# 数据类定义
# ============================================================


@dataclass
class BypassResult:
    """绕过结果"""

    success: bool = False
    url: str = ""
    final_url: str = ""
    cookies: Dict[str, str] = field(default_factory=dict)
    cf_clearance: str = ""
    user_agent: str = ""
    title: str = ""
    duration: float = 0
    error: str = ""


# ============================================================
# 日志工具（支持静默模式）
# ============================================================


class Logger:
    """日志工具，支持静默模式"""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def log(self, msg: str):
        if not self.quiet:
            print(msg, file=sys.stderr)

    def info(self, msg: str):
        self.log(f"[*] {msg}")

    def success(self, msg: str):
        self.log(f"[✓] {msg}")

    def error(self, msg: str):
        self.log(f"[!] {msg}")

    def warning(self, msg: str):
        self.log(f"[!] {msg}")

    def debug(self, msg: str):
        self.log(f"[DEBUG] {msg}")


# ============================================================
# 主类：Cloudflare 绕过器
# ============================================================


class CloudflareBypassDocker:
    """Cloudflare 人机验证绕过器 - Docker 版本"""

    CF_VERIFICATION_TITLES = [
        "请稍候",
        "just a moment",
        "attention required",
        "checking your browser",
        "verifying you are human",
        "one more step",
        "please wait",
    ]

    def __init__(
        self,
        url: str,
        wait_time: int = 5,
        max_wait: int = 50,
        max_retries: int = 1,
        quiet: bool = False,
        browser: str = "auto",  # auto, chrome, chromium
    ):
        self.url = url
        self.wait_time = wait_time
        self.max_wait = max_wait
        self.max_retries = max_retries
        self.quiet = quiet
        self.browser = browser

        self.driver = None
        self.logger = Logger(quiet=quiet)
        self.result = BypassResult(url=url)

        # 检查 PyAutoGUI 状态
        if not PYAUTOGUI_AVAILABLE:
            self.logger.debug(f"PyAutoGUI 不可用: {PYAUTOGUI_ERROR or '未知错误'}")
        else:
            self.logger.debug("PyAutoGUI 已就绪，将使用真实鼠标移动")

    def _get_browser_version(self, browser_path: str) -> int:
        """获取浏览器主版本号"""
        import subprocess

        try:
            result = subprocess.run(
                [browser_path, "--version"], capture_output=True, text=True, timeout=10
            )
            # 输出格式: "Chromium 145.0.7629.0" 或 "Google Chrome 143.0.xxx"
            version_str = result.stdout.strip()
            self.logger.debug(f"浏览器版本字符串: {version_str}")

            # 提取主版本号
            import re

            match = re.search(r"(\d+)\.", version_str)
            if match:
                return int(match.group(1))
        except Exception as e:
            self.logger.error(f"获取浏览器版本失败: {e}")

        return None  # 返回 None 让 undetected-chromedriver 自动检测

    def _detect_snap_chromium(self, browser_path: str) -> bool:
        """检测是否为 Snap 包的 Chromium"""
        try:
            result = subprocess.run(
                [browser_path, "--version"], capture_output=True, text=True, timeout=10
            )
            return "snap" in result.stdout.lower()
        except Exception:
            return False

    def _diagnose_environment(self):
        """诊断运行环境"""
        self.logger.info("=== 环境诊断 ===")

        # 检查 DISPLAY
        display = os.environ.get("DISPLAY")
        self.logger.info(f"DISPLAY: {display or '未设置'}")

        # 检查用户
        user = os.environ.get("USER", "unknown")
        self.logger.info(f"当前用户: {user}")
        if user == "root":
            self.logger.warning("以 root 用户运行,确保使用 --no-sandbox")

        self.logger.info("================")

    def _setup_driver(self):
        """配置 undetected-chromedriver"""
        self.logger.info("初始化浏览器...")

        # 诊断环境
        self._diagnose_environment()

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Docker 环境特定设置
        options.add_argument("--disable-setuid-sandbox")

        # 新增: 解决 root 环境和 Snap 包问题
        options.add_argument("--remote-debugging-port=0")  # 避免端口冲突
        options.add_argument("--disable-features=VizDisplayCompositor")  # Snap 兼容
        options.add_argument("--disable-backgrounding-occluded-windows")  # 防止后台挂起
        options.add_argument("--disable-renderer-backgrounding")  # 保持渲染活跃
        options.add_argument("--disable-background-timer-throttling")  # 防止计时器节流

        # 确定使用哪个浏览器
        browser_path = None

        if self.browser == "chromium":
            # 强制使用 Chromium，自动检测版本
            self.logger.info("使用本地 Chromium")

            # 查找 Chromium 路径(优先级:标准安装 > Snap)
            chromium_paths = [
                "/Applications/Chromium.app/Contents/MacOS/Chromium",  # macOS
                "/usr/bin/chromium",  # Linux 标准安装
                "/usr/bin/chromium-browser",  # Linux (可能是 wrapper)
                "/snap/bin/chromium",  # Snap 包(最后尝试)
            ]
            chromium_path = None
            for path in chromium_paths:
                if os.path.exists(path):
                    # 检查是否为 Snap 包
                    if self._detect_snap_chromium(path):
                        self.logger.warning(f"检测到 Snap 包 Chromium: {path}")
                        self.logger.warning(
                            "Snap 包可能导致兼容性问题,建议安装 .deb 版本的 Chrome/Chromium"
                        )
                    chromium_path = path
                    break

            if not chromium_path:
                raise RuntimeError(
                    "Chromium 未安装,请先安装:apt install chromium-browser 或 "
                    "wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && "
                    "apt install ./google-chrome-stable_current_amd64.deb"
                )

            # 关键修复:设置二进制路径
            options.binary_location = chromium_path
            self.logger.info(f"设置 Chromium 路径: {chromium_path}")

            # 获取 Chromium 版本号
            browser_version = self._get_browser_version(chromium_path)
            if browser_version:
                self.logger.info(f"检测到 Chromium 版本: {browser_version}")
                try:
                    driver = uc.Chrome(options=options, version_main=browser_version)
                except Exception as e:
                    self.logger.error(f"启动浏览器失败: {e}")
                    # 提供诊断信息
                    if chromium_path and self._detect_snap_chromium(chromium_path):
                        self.logger.error("检测到使用 Snap 包,这是已知问题")
                        self.logger.error("解决方案:")
                        self.logger.error("1. 移除 Snap Chromium: snap remove chromium")
                        self.logger.error("2. 安装 Google Chrome: wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && apt install ./google-chrome-stable_current_amd64.deb")
                    if not os.environ.get("DISPLAY"):
                        self.logger.error("DISPLAY 环境变量未设置")
                    raise
            else:
                self.logger.warning("无法获取 Chromium 版本，使用自动检测")
                try:
                    driver = uc.Chrome(options=options, version_main=None)
                except Exception as e:
                    self.logger.error(f"启动浏览器失败: {e}")
                    # 提供诊断信息
                    if chromium_path and self._detect_snap_chromium(chromium_path):
                        self.logger.error("检测到使用 Snap 包,这是已知问题")
                        self.logger.error("解决方案:")
                        self.logger.error("1. 移除 Snap Chromium: snap remove chromium")
                        self.logger.error("2. 安装 Google Chrome: wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && apt install ./google-chrome-stable_current_amd64.deb")
                    if not os.environ.get("DISPLAY"):
                        self.logger.error("DISPLAY 环境变量未设置")
                    raise

            return driver

        elif self.browser == "chrome":
            # 强制使用 Chrome，自动检测版本
            self.logger.info("使用本地 Chrome")

            # 尝试找到 Chrome 路径
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
                "/usr/bin/google-chrome",  # Linux
                "/usr/bin/google-chrome-stable",  # Linux (alternative)
            ]
            chrome_path = None
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_path = path
                    break

            # 如果找到了 Chrome 路径，获取版本号
            if chrome_path:
                browser_version = self._get_browser_version(chrome_path)
                # 关键修复:设置二进制路径
                options.binary_location = chrome_path
                self.logger.info(f"设置 Chrome 路径: {chrome_path}")
                if browser_version:
                    self.logger.info(f"检测到 Chrome 版本: {browser_version}")
                    try:
                        driver = uc.Chrome(options=options, version_main=browser_version)
                    except Exception as e:
                        self.logger.error(f"启动浏览器失败: {e}")
                        if not os.environ.get("DISPLAY"):
                            self.logger.error("DISPLAY 环境变量未设置")
                        raise
                else:
                    self.logger.warning("无法获取 Chrome 版本，使用自动检测")
                    try:
                        driver = uc.Chrome(options=options, version_main=None)
                    except Exception as e:
                        self.logger.error(f"启动浏览器失败: {e}")
                        if not os.environ.get("DISPLAY"):
                            self.logger.error("DISPLAY 环境变量未设置")
                        raise
            else:
                # 没找到路径，让 undetected-chromedriver 自动检测
                self.logger.info("未找到 Chrome 路径，使用自动检测")
                try:
                    driver = uc.Chrome(options=options, version_main=None)
                except Exception as e:
                    self.logger.error(f"启动浏览器失败: {e}")
                    if not os.environ.get("DISPLAY"):
                        self.logger.error("DISPLAY 环境变量未设置")
                    raise

            return driver

        else:  # auto
            # 自动检测：优先使用环境变量，其次使用默认 Chrome
            browser_path = os.environ.get("CHROME_BIN")
            if browser_path and not os.path.exists(browser_path):
                browser_path = None

        if browser_path:
            # 使用指定的浏览器路径
            self.logger.info(f"使用浏览器: {browser_path}")
            options.binary_location = browser_path
            options.add_argument("--disable-software-rasterizer")

            # 获取浏览器版本号
            browser_version = self._get_browser_version(browser_path)
            self.logger.info(f"浏览器版本: {browser_version}")

            # 检查是否有系统 chromedriver（Docker 环境）
            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
            if chromedriver_path and os.path.exists(chromedriver_path):
                self.logger.info(f"使用系统 chromedriver: {chromedriver_path}")
                try:
                    driver = uc.Chrome(
                        options=options,
                        browser_executable_path=browser_path,
                        driver_executable_path=chromedriver_path,
                        version_main=browser_version,
                    )
                except Exception as e:
                    self.logger.error(f"启动浏览器失败: {e}")
                    if not os.environ.get("DISPLAY"):
                        self.logger.error("DISPLAY 环境变量未设置")
                    raise
            else:
                try:
                    driver = uc.Chrome(
                        options=options,
                        browser_executable_path=browser_path,
                        version_main=browser_version,
                    )
                except Exception as e:
                    self.logger.error(f"启动浏览器失败: {e}")
                    if not os.environ.get("DISPLAY"):
                        self.logger.error("DISPLAY 环境变量未设置")
                    raise
        else:
            # 默认：让 undetected-chromedriver 自动使用系统 Chrome
            self.logger.info("使用本地 Chrome (默认)")
            try:
                driver = uc.Chrome(options=options, version_main=None)
            except Exception as e:
                self.logger.error(f"启动浏览器失败: {e}")
                if not os.environ.get("DISPLAY"):
                    self.logger.error("DISPLAY 环境变量未设置")
                raise

        return driver

    def _is_verification_present(self) -> bool:
        """检测是否仍在验证页面"""
        try:
            title = (self.driver.title or "").lower()
            return any(kw in title for kw in self.CF_VERIFICATION_TITLES)
        except Exception:
            return True

    def _has_cf_clearance(self) -> bool:
        """检查是否获得了 cf_clearance cookie"""
        try:
            cookies = self.driver.get_cookies()
            return any(c["name"] == "cf_clearance" for c in cookies)
        except Exception:
            return False

    def _get_all_cookies(self) -> Dict[str, str]:
        """获取所有 cookies"""
        try:
            cookies = self.driver.get_cookies()
            return {c["name"]: c["value"] for c in cookies}
        except Exception:
            return {}

    def _get_user_agent(self) -> str:
        """获取 User-Agent"""
        try:
            return self.driver.execute_script("return navigator.userAgent")
        except Exception:
            return ""

    def _find_cloudflare_iframe(self) -> Optional[Dict]:
        """查找 Cloudflare Turnstile iframe"""
        try:
            js_find_iframes = """
            function findAllIframes(root = document) {
                let iframes = [];
                let currentIframes = Array.from(root.querySelectorAll('iframe'));
                for (let iframe of currentIframes) {
                    iframes.push({
                        id: iframe.id || '',
                        src: iframe.src || '',
                        visible: iframe.offsetParent !== null
                    });
                }
                let allElements = root.querySelectorAll('*');
                for (let element of allElements) {
                    if (element.shadowRoot) {
                        let shadowIframes = findAllIframes(element.shadowRoot);
                        iframes = iframes.concat(shadowIframes);
                    }
                }
                return iframes;
            }
            return findAllIframes();
            """

            js_iframes = self.driver.execute_script(js_find_iframes)

            for iframe_data in js_iframes:
                iframe_id = iframe_data.get("id", "")
                iframe_src = iframe_data.get("src", "")

                is_cf = (
                    iframe_id.startswith("cf-chl-widget")
                    or "challenges.cloudflare.com" in iframe_src
                    or "turnstile" in iframe_src.lower()
                )

                if is_cf:
                    # 用 Selenium 重新定位
                    if iframe_id:
                        try:
                            element = self.driver.find_element(By.ID, iframe_id)
                            return {
                                "id": iframe_id,
                                "src": iframe_src,
                                "element": element,
                            }
                        except Exception:
                            pass
                    try:
                        element = self.driver.find_element(
                            By.CSS_SELECTOR, 'iframe[src*="challenges.cloudflare"]'
                        )
                        return {"id": iframe_id, "src": iframe_src, "element": element}
                    except Exception:
                        pass

            return None
        except Exception:
            return None

    def _click_turnstile_checkbox(self, iframe_info: Dict) -> bool:
        """在 Turnstile iframe 中点击复选框"""
        iframe_element = iframe_info.get("element")
        if not iframe_element:
            return False

        try:
            self.driver.switch_to.frame(iframe_element)
            time.sleep(1)

            checkbox_selectors = [
                'input[type="checkbox"]',
                "#cf-chl-cb-i",
                ".ctp-checkbox-label",
                "label",
                '[role="checkbox"]',
                "body",
            ]

            clicked = False
            for selector in checkbox_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            time.sleep(random.uniform(0.1, 0.3))
                            elem.click()
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    continue

            self.driver.switch_to.default_content()
            return clicked

        except Exception:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            return False

    # ============================================================
    # PyAutoGUI 鼠标操作
    # ============================================================

    def _bezier_curve(
        self, start: tuple, end: tuple, num_points: int = 50
    ) -> List[tuple]:
        """生成贝塞尔曲线路径"""
        import math

        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.sqrt(dx**2 + dy**2)

        if distance < 5:
            return [start, end]

        perp_x = dy / distance
        perp_y = -dx / distance

        min_offset = random.uniform(20, 50)
        max_offset = max(distance * 0.4, min_offset)
        offset_magnitude = random.uniform(min_offset, max_offset)
        direction = random.choice([-1, 1])
        offset = direction * offset_magnitude

        control = (mid_x + perp_x * offset, mid_y + perp_y * offset)

        points = []
        for i in range(num_points + 1):
            t = i / num_points
            x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0]
            y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1]
            points.append((x, y))

        return points

    def _human_like_move(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5
    ) -> None:
        """人类化鼠标移动"""
        num_points = random.randint(40, 60)
        points = self._bezier_curve((start_x, start_y), (end_x, end_y), num_points)

        # 添加随机抖动
        jittered = []
        for i, (x, y) in enumerate(points):
            if i == 0 or i == len(points) - 1:
                jittered.append((x, y))
            else:
                jx = x + random.gauss(0, 1.5)
                jy = y + random.gauss(0, 1.5)
                jittered.append((jx, jy))
        points = jittered

        total_points = len(points)

        for i, (x, y) in enumerate(points):
            progress = i / (total_points - 1) if total_points > 1 else 1
            pyautogui.moveTo(int(x), int(y), _pause=False)

            if i < total_points - 1:
                base_delay = duration / total_points
                if progress < 0.2 or progress > 0.8:
                    delay = base_delay * random.uniform(1.5, 2.0)
                else:
                    delay = base_delay * random.uniform(0.5, 1.0)
                time.sleep(delay)

    def _get_browser_chrome_height(self) -> int:
        """估算浏览器工具栏高度"""
        try:
            window_size = self.driver.get_window_size()
            viewport_height = self.driver.execute_script("return window.innerHeight")
            return window_size["height"] - viewport_height
        except Exception:
            return 85

    def _try_click_checkbox_by_position(self) -> bool:
        """通过坐标点击复选框区域（使用 PyAutoGUI 操作系统级点击）"""
        self.logger.info("尝试通过坐标点击复选框区域...")

        # 获取 Turnstile 容器位置
        try:
            checkbox_info = self.driver.execute_script("""
                var result = {};
                
                // 方法1: 查找 Turnstile widget（300x65 左右）
                var allElements = document.querySelectorAll('*');
                for (var el of allElements) {
                    var rect = el.getBoundingClientRect();
                    if (rect.width >= 290 && rect.width <= 320 && 
                        rect.height >= 60 && rect.height <= 75 &&
                        rect.top > 0) {
                        result.found = true;
                        result.x = rect.left;
                        result.y = rect.top;
                        result.width = rect.width;
                        result.height = rect.height;
                        result.tag = el.tagName;
                        result.id = el.id;
                        result.isWidget = true;
                        break;
                    }
                }
                
                // 方法2: 使用 cqfu9 容器
                if (!result.found) {
                    var container = document.querySelector('#cqfu9, [id*="cqfu"]');
                    if (container) {
                        var rect = container.getBoundingClientRect();
                        result.found = true;
                        result.x = rect.left;
                        result.y = rect.top;
                        result.width = rect.width;
                        result.height = rect.height;
                        result.isContainer = true;
                    }
                }
                
                // 方法3: 查找 cf-turnstile 相关元素
                if (!result.found) {
                    var selectors = ['.cf-turnstile', '[class*="turnstile"]', '[id*="turnstile"]'];
                    for (var sel of selectors) {
                        var el = document.querySelector(sel);
                        if (el) {
                            var rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                result.found = true;
                                result.x = rect.left;
                                result.y = rect.top;
                                result.width = rect.width;
                                result.height = rect.height;
                                result.selector = sel;
                                result.isContainer = true;
                                break;
                            }
                        }
                    }
                }

                // 方法4: 通过 hidden input 反查容器（最通用的方法）
                if (!result.found) {
                    var input = document.querySelector('input[type="hidden"][name="cf-turnstile-response"]');
                    if (input) {
                        // 向上查找包含 display: grid 的父容器
                        var parent = input.parentElement;
                        while (parent && parent !== document.body) {
                            var style = window.getComputedStyle(parent);
                            var display = style.display;

                            // 检查是否是网格布局容器
                            if (display === 'grid' || parent.style.display === 'grid') {
                                var rect = parent.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    result.found = true;
                                    result.x = rect.left;
                                    result.y = rect.top;
                                    result.width = rect.width;
                                    result.height = rect.height;
                                    result.tag = parent.tagName;
                                    result.id = parent.id;
                                    result.isContainer = true;
                                    result.method = 'hidden-input';
                                    break;
                                }
                            }

                            parent = parent.parentElement;
                        }
                    }
                }

                // 方法5: 兜底 - 查找任何带随机 ID 的 grid 容器
                if (!result.found) {
                    var gridContainers = document.querySelectorAll('div[style*="display: grid"], div[style*="display:grid"]');
                    for (var container of gridContainers) {
                        // 检查是否包含 template 或 hidden input
                        var hasTemplate = container.querySelector('template');
                        var hasInput = container.querySelector('input[type="hidden"][name="cf-turnstile-response"]');

                        if (hasTemplate || hasInput) {
                            var rect = container.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && rect.top > 0) {
                                result.found = true;
                                result.x = rect.left;
                                result.y = rect.top;
                                result.width = rect.width;
                                result.height = rect.height;
                                result.tag = container.tagName;
                                result.id = container.id;
                                result.isContainer = true;
                                result.method = 'grid-style';
                                break;
                            }
                        }
                    }
                }

                return result;
            """)

            if checkbox_info and checkbox_info.get("found"):
                element_type = "widget" if checkbox_info.get("isWidget") else "容器"
                self.logger.info(
                    f"找到 Turnstile {element_type}: {checkbox_info.get('tag', '')}#{checkbox_info.get('id', '')}"
                )
                self.logger.info(
                    f"元素位置: x={checkbox_info['x']:.0f}, y={checkbox_info['y']:.0f}, "
                    + f"w={checkbox_info['width']:.0f}, h={checkbox_info['height']:.0f}"
                )

                location = {"x": checkbox_info["x"], "y": checkbox_info["y"]}
                size = {
                    "width": checkbox_info["width"],
                    "height": checkbox_info["height"],
                }
                is_container = checkbox_info.get("isContainer", False)

                # 使用 PyAutoGUI 操作系统级点击
                if PYAUTOGUI_AVAILABLE:
                    self.logger.debug("使用 PyAutoGUI 进行鼠标移动和点击")
                    return self._click_with_pyautogui(location, size, is_container)
                else:
                    self.logger.warning(
                        f"PyAutoGUI 不可用 ({PYAUTOGUI_ERROR or '未安装'})，使用 JavaScript 点击"
                    )
                    return self._click_with_javascript(location, size, is_container)
            else:
                self.logger.info("JavaScript 方法未找到元素，尝试 Selenium 查找...")

        except Exception as e:
            self.logger.error(f"JavaScript 定位失败: {e}")

        # 备用方法: 使用 Selenium 查找
        container = None
        selectors = ["#cqfu9", '[id*="cqfu"]', ".cf-turnstile", '[class*="turnstile"]']

        for sel in selectors:
            try:
                container = self.driver.find_element(By.CSS_SELECTOR, sel)
                if container:
                    self.logger.info(f"找到容器: {sel}")
                    break
            except Exception:
                continue

        if not container:
            self.logger.error("未找到 Turnstile 容器")
            return False

        # 获取视口坐标
        try:
            viewport_location = self.driver.execute_script(
                """
                var el = arguments[0];
                var rect = el.getBoundingClientRect();
                return {x: rect.left, y: rect.top, width: rect.width, height: rect.height};
            """,
                container,
            )
            location = {"x": viewport_location["x"], "y": viewport_location["y"]}
            size = {
                "width": viewport_location["width"],
                "height": viewport_location["height"],
            }
        except Exception:
            location = container.location
            size = container.size

        self.logger.info(
            f"容器视口位置: x={location['x']}, y={location['y']}, w={size['width']}, h={size['height']}"
        )

        if PYAUTOGUI_AVAILABLE:
            self.logger.debug("使用 PyAutoGUI 进行鼠标移动和点击")
            return self._click_with_pyautogui(location, size, is_container=True)
        else:
            self.logger.warning(
                f"PyAutoGUI 不可用 ({PYAUTOGUI_ERROR or '未安装'})，使用 JavaScript 点击"
            )
            return self._click_with_javascript(location, size, is_container=True)

    def _click_with_pyautogui(
        self, element_location: dict, element_size: dict, is_container: bool = False
    ) -> bool:
        """使用 PyAutoGUI 模拟真实鼠标点击（多点策略）"""
        self.logger.info("使用 PyAutoGUI 操作系统级鼠标点击...")

        try:
            # 获取浏览器窗口位置
            window_pos = self.driver.get_window_position()
            window_x = window_pos["x"]
            window_y = window_pos["y"]
            self.logger.debug(f"浏览器窗口位置: x={window_x}, y={window_y}")

            # 获取浏览器工具栏高度
            chrome_height = self._get_browser_chrome_height()

            # 获取视口信息
            viewport_info = self.driver.execute_script("""
                return {
                    innerWidth: window.innerWidth,
                    innerHeight: window.innerHeight,
                    scrollX: window.scrollX,
                    scrollY: window.scrollY
                };
            """)
            self.logger.debug(
                f"视口: {viewport_info['innerWidth']}x{viewport_info['innerHeight']}, 滚动: ({viewport_info['scrollX']}, {viewport_info['scrollY']})"
            )

            # 元素位置是视口坐标（getBoundingClientRect 返回的）
            elem_x = element_location["x"]
            elem_y = element_location["y"]
            elem_w = element_size["width"]
            elem_h = element_size["height"]

            # 计算屏幕坐标
            # 屏幕坐标 = 窗口位置 + 工具栏高度 + 元素视口坐标
            base_screen_x = window_x + elem_x
            base_screen_y = window_y + chrome_height + elem_y

            self.logger.debug(f"元素视口坐标: ({elem_x:.0f}, {elem_y:.0f})")
            self.logger.debug(
                f"基准屏幕坐标: ({base_screen_x:.0f}, {base_screen_y:.0f})"
            )

            # 计算多个可能的点击位置
            click_positions = []
            click_y = int(base_screen_y + elem_h // 2)

            if is_container and elem_w > 400:
                # 大容器，Turnstile widget 通常在容器左侧
                click_positions = [
                    (int(base_screen_x + 25), click_y),
                    (int(base_screen_x + 15), click_y),
                    (int(base_screen_x + 35), click_y),
                    (int(base_screen_x + 45), click_y),
                    (int(base_screen_x + 55), click_y),
                    (int(base_screen_x + 65), click_y),
                    (int(base_screen_x + elem_w // 2 - 125), click_y),
                ]
            else:
                # 小元素或精确的 widget
                click_positions = [
                    (int(base_screen_x + 25), click_y),
                    (int(base_screen_x + 15), click_y),
                    (int(base_screen_x + 35), click_y),
                    (int(base_screen_x + 50), click_y),
                ]

            self.logger.info(f"将尝试 {len(click_positions)} 个屏幕位置...")

            for i, (screen_x, screen_y) in enumerate(click_positions):
                self.logger.info(f"点击 #{i + 1} 屏幕坐标: ({screen_x}, {screen_y})")

                # 随机化点击位置
                jitter_x = random.randint(-2, 2)
                jitter_y = random.randint(-2, 2)
                final_x = screen_x + jitter_x
                final_y = screen_y + jitter_y

                # 获取当前鼠标位置
                current_x, current_y = pyautogui.position()

                # 人类化移动
                move_duration = random.uniform(0.4, 0.7)
                self._human_like_move(
                    current_x, current_y, final_x, final_y, move_duration
                )

                # 模拟反应时间
                reaction_time = random.uniform(0.1, 0.3)
                time.sleep(reaction_time)

                # 点击
                pyautogui.click()
                self.logger.success(f"点击 #{i + 1} 完成")

                # 等待看效果
                time.sleep(0.8)

                # 检查是否成功
                if self._has_cf_clearance() or not self._is_verification_present():
                    self.logger.success(f"点击 #{i + 1} 成功！验证已通过")
                    return True

            self.logger.info("所有点击位置都尝试过了，继续等待...")
            return True  # 返回 True 继续等待

        except Exception as e:
            self.logger.error(f"PyAutoGUI 点击失败: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _click_with_javascript(
        self, element_location: dict, element_size: dict, is_container: bool = False
    ) -> bool:
        """使用 JavaScript 点击"""
        self.logger.info("使用 JavaScript 点击...")

        try:
            base_y = int(element_location["y"] + element_size["height"] // 2)

            click_positions = []
            if is_container and element_size["width"] > 400:
                container_center_x = element_location["x"] + element_size["width"] // 2
                click_positions = [
                    (int(container_center_x - 150 + 25), base_y),
                    (int(container_center_x - 125), base_y),
                    (int(element_location["x"] + 25), base_y),
                ]
            else:
                click_positions = [
                    (int(element_location["x"] + 25), base_y),
                    (int(element_location["x"] + 15), base_y),
                ]

            for click_x, click_y in click_positions:
                self.driver.execute_script(f"""
                    var element = document.elementFromPoint({click_x}, {click_y});
                    if (element) {{
                        element.click();
                        var event = new MouseEvent('click', {{
                            view: window, bubbles: true, cancelable: true,
                            clientX: {click_x}, clientY: {click_y}
                        }});
                        element.dispatchEvent(event);
                    }}
                """)

                time.sleep(0.5)

                if self._has_cf_clearance() or not self._is_verification_present():
                    return True

            return True

        except Exception as e:
            self.logger.error(f"JavaScript 点击失败: {e}")
            return False

    def _smart_wait_for_turnstile(self, timeout: int = 30) -> dict:
        """
        智能等待 Turnstile 加载完成

        Returns:
            dict: {
                'ready': bool,  # 是否准备好（找到 iframe 或已通过）
                'passed': bool,  # 是否已通过验证
                'iframe': dict or None,  # iframe 信息
                'method': str  # 检测方法
            }
        """
        self.logger.info(f"智能等待 Turnstile 加载（最长 {timeout} 秒）...")

        start_time = time.time()
        check_count = 0

        while time.time() - start_time < timeout:
            check_count += 1
            elapsed = time.time() - start_time

            # 1. 检查是否已经获得 cf_clearance（已通过）
            if self._has_cf_clearance():
                self.logger.success(f"已获得 cf_clearance! (耗时 {elapsed:.1f}s)")
                return {
                    "ready": True,
                    "passed": True,
                    "iframe": None,
                    "method": "cf_clearance",
                }

            # 2. 检查页面标题是否已变化（验证已通过）
            if not self._is_verification_present():
                self.logger.success(f"验证页面已消失! (耗时 {elapsed:.1f}s)")
                return {
                    "ready": True,
                    "passed": True,
                    "iframe": None,
                    "method": "title_changed",
                }

            # 3. 检查 Turnstile iframe 是否出现
            cf_iframe = self._find_cloudflare_iframe()
            if cf_iframe:
                self.logger.success(f"找到 Turnstile iframe! (耗时 {elapsed:.1f}s)")
                return {
                    "ready": True,
                    "passed": False,
                    "iframe": cf_iframe,
                    "method": "iframe_found",
                }

            # 4. 检查是否有可点击的 widget 元素
            widget_info = self._check_widget_exists()
            if widget_info:
                self.logger.success(f"找到 Turnstile widget! (耗时 {elapsed:.1f}s)")
                return {
                    "ready": True,
                    "passed": False,
                    "iframe": None,
                    "method": "widget_found",
                    "widget": widget_info,
                }

            # 每 3 秒打印一次状态
            if check_count % 6 == 0:
                self.logger.info(f"等待中... ({elapsed:.1f}s/{timeout}s)")

            time.sleep(0.5)

        self.logger.error(f"等待超时 ({timeout}s)，未检测到 Turnstile")
        return {"ready": False, "passed": False, "iframe": None, "method": "timeout"}

    def _check_widget_exists(self) -> Optional[dict]:
        """检查 Turnstile widget 是否存在"""
        try:
            result = self.driver.execute_script("""
                // 方法1: 查找 300x65 大小的 widget
                var allElements = document.querySelectorAll('*');
                for (var el of allElements) {
                    var rect = el.getBoundingClientRect();
                    if (rect.width >= 290 && rect.width <= 320 && 
                        rect.height >= 60 && rect.height <= 75 &&
                        rect.top > 0 && el.offsetParent !== null) {
                        return {
                            found: true,
                            x: rect.left,
                            y: rect.top,
                            width: rect.width,
                            height: rect.height,
                            tag: el.tagName,
                            id: el.id
                        };
                    }
                }
                
                // 方法2: 查找 turnstile 相关容器
                var selectors = ['#cqfu9', '[id*="cqfu"]', '.cf-turnstile', '[class*="turnstile"]'];
                for (var sel of selectors) {
                    var el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) {
                        var rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            return {
                                found: true,
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height,
                                selector: sel
                            };
                        }
                    }
                }

                // 方法3: 通过 hidden input 反查容器
                var input = document.querySelector('input[type="hidden"][name="cf-turnstile-response"]');
                if (input) {
                    var parent = input.parentElement;
                    while (parent && parent !== document.body) {
                        var style = window.getComputedStyle(parent);
                        var display = style.display;

                        if (display === 'grid' || parent.style.display === 'grid') {
                            var rect = parent.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && rect.top > 0) {
                                return {
                                    found: true,
                                    x: rect.left,
                                    y: rect.top,
                                    width: rect.width,
                                    height: rect.height,
                                    tag: parent.tagName,
                                    id: parent.id,
                                    method: 'hidden-input'
                                };
                            }
                        }

                        parent = parent.parentElement;
                    }
                }

                // 方法4: 查找 grid 容器
                var gridContainers = document.querySelectorAll('div[style*="display: grid"], div[style*="display:grid"]');
                for (var container of gridContainers) {
                    var hasTemplate = container.querySelector('template');
                    var hasInput = container.querySelector('input[type="hidden"][name="cf-turnstile-response"]');

                    if (hasTemplate || hasInput) {
                        var rect = container.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.top > 0) {
                            return {
                                found: true,
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height,
                                tag: container.tagName,
                                id: container.id,
                                method: 'grid-style'
                            };
                        }
                    }
                }

                return null;
            """)
            return result if result and result.get("found") else None
        except Exception:
            return None

    def _wait_for_verification(self) -> bool:
        """等待验证完成（智能版）"""
        # 第一阶段：智能等待 Turnstile 加载
        wait_result = self._smart_wait_for_turnstile(timeout=min(30, self.max_wait))

        if wait_result["passed"]:
            # 已经通过验证
            return True

        if not wait_result["ready"]:
            # 超时未检测到 Turnstile
            self.logger.error("未检测到 Turnstile，可能页面结构不同")
            return False

        # 第二阶段：尝试点击并等待验证完成
        self.logger.info("开始尝试点击验证...")

        start_time = time.time()
        iframe_clicked = False
        position_clicked = False
        click_attempts = 0
        max_click_attempts = 3

        while True:
            elapsed = time.time() - start_time

            if elapsed >= self.max_wait:
                self.logger.error(f"等待超时 ({self.max_wait}秒)")
                return False

            if self._has_cf_clearance():
                self.logger.success(f"获得 cf_clearance! (总耗时 {int(elapsed)} 秒)")
                return True

            if not self._is_verification_present():
                self.logger.success(f"验证页面消失! (总耗时 {int(elapsed)} 秒)")
                return True

            # 尝试点击（限制尝试次数）
            if click_attempts < max_click_attempts:
                if not iframe_clicked and not position_clicked:
                    # 先尝试 iframe 点击
                    if wait_result.get("iframe"):
                        self.logger.info(
                            f"尝试 iframe 点击 (第 {click_attempts + 1} 次)..."
                        )
                        if self._click_turnstile_checkbox(wait_result["iframe"]):
                            iframe_clicked = True
                            click_attempts += 1
                    else:
                        # 尝试坐标点击
                        self.logger.info(
                            f"尝试坐标点击 (第 {click_attempts + 1} 次)..."
                        )
                        if self._try_click_checkbox_by_position():
                            position_clicked = True
                            click_attempts += 1

                    # 点击后等待 3 秒看效果
                    time.sleep(3)
                elif iframe_clicked or position_clicked:
                    # 已经点击过，如果 5 秒内没有通过，再尝试点击
                    if int(elapsed) % 5 == 0 and click_attempts < max_click_attempts:
                        self.logger.info(
                            f"重新尝试点击 (第 {click_attempts + 1} 次)..."
                        )
                        if self._try_click_checkbox_by_position():
                            click_attempts += 1
                        time.sleep(3)

            time.sleep(0.5)

    def bypass(self) -> BypassResult:
        """执行绕过操作"""
        start_time = time.time()

        self.logger.info(f"目标 URL: {self.url}")
        self.logger.info(f"初始等待: {self.wait_time} 秒")
        self.logger.info(f"最大等待: {self.max_wait} 秒")

        try:
            for attempt in range(1, self.max_retries + 1):
                self.logger.info(f"尝试 #{attempt}/{self.max_retries}")

                if self.driver is None:
                    self.driver = self._setup_driver()

                self.logger.info(f"访问: {self.url}")
                self.driver.get(self.url)

                # 短暂等待页面开始加载（2秒足够）
                self.logger.info("等待页面开始加载...")
                time.sleep(2)

                # 快速检查是否无需验证
                if not self._is_verification_present():
                    self.logger.success("无需验证，页面直接可访问")
                    self.result.success = True
                    break

                if self._has_cf_clearance():
                    self.logger.success("已有 cf_clearance，验证已通过")
                    self.result.success = True
                    break

                # 智能等待并完成验证
                self.logger.info("检测到 Cloudflare 验证，开始智能等待...")
                if self._wait_for_verification():
                    self.logger.success("验证通过！")
                    time.sleep(2)
                    self.result.success = True
                    break
                else:
                    self.logger.error(f"尝试 #{attempt} 失败")
                    if attempt < self.max_retries:
                        self.driver.refresh()
                        time.sleep(3)

        except Exception as e:
            self.result.error = str(e)
            self.logger.error(f"异常: {e}")

        finally:
            self.result.duration = round(time.time() - start_time, 2)

            if self.driver:
                try:
                    self.result.final_url = self.driver.current_url
                    self.result.title = self.driver.title
                    self.result.cookies = self._get_all_cookies()
                    self.result.cf_clearance = self.result.cookies.get(
                        "cf_clearance", ""
                    )
                    self.result.user_agent = self._get_user_agent()
                except Exception:
                    pass

                try:
                    self.driver.quit()
                except Exception:
                    pass

        return self.result


# ============================================================
# 主函数
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Cloudflare 绕过工具 - Docker 版本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("url", help="目标 URL")
    parser.add_argument(
        "--wait", type=int, default=5, help="初始等待时间（秒），默认 5"
    )
    parser.add_argument(
        "--max-wait", type=int, default=50, help="最大等待时间（秒），默认 50"
    )
    parser.add_argument("--retry", type=int, default=1, help="最大重试次数，默认 1")
    parser.add_argument("--output-json", action="store_true", help="输出纯 JSON 格式")
    parser.add_argument(
        "--browser",
        type=str,
        default="auto",
        choices=["auto", "chrome", "chromium"],
        help="浏览器选择：auto(自动), chrome, chromium",
    )

    args = parser.parse_args()

    # JSON 模式下静默日志
    quiet = args.output_json

    bypasser = CloudflareBypassDocker(
        url=args.url,
        wait_time=args.wait,
        max_wait=args.max_wait,
        max_retries=args.retry,
        quiet=quiet,
        browser=args.browser,
    )

    result = bypasser.bypass()

    # 输出结果
    if args.output_json:
        # JSON 模式：只输出 JSON 到 stdout
        output = {
            "success": result.success,
            "url": result.url,
            "final_url": result.final_url,
            "cookies": result.cookies,
            "cf_clearance": result.cf_clearance,
            "user_agent": result.user_agent,
            "title": result.title,
            "duration": result.duration,
            "error": result.error,
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        # 普通模式：打印报告
        print("\n" + "=" * 60)
        print("结果报告")
        print("=" * 60)
        print(f"状态: {'✓ 成功' if result.success else '✗ 失败'}")
        print(f"目标 URL: {result.url}")
        print(f"最终 URL: {result.final_url}")
        print(f"标题: {result.title}")
        print(f"耗时: {result.duration} 秒")
        print(
            f"cf_clearance: {result.cf_clearance}"
            if result.cf_clearance
            else "cf_clearance: 无"
        )
        print(
            f"User-Agent: {result.user_agent}"
            if result.user_agent
            else "User-Agent: 无"
        )
        if result.error:
            print(f"错误: {result.error}")
        print("=" * 60)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
