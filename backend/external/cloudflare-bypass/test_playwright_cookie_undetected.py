#!/usr/bin/env python3
"""Playwright Cookie 验证脚本（基于 test_undetected_cookie.py）

使用 Playwright（与 test_undetected_cookie.py 相同的测试值和验证逻辑）验证提供的
user_agent 和 cf_clearance cookie 是否能成功访问目标网站。
使用现有的 Chromium 浏览器。
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright

# Cloudflare 挑战页面的关键词（用于检测是否仍被拦截）
CF_CHALLENGE_KEYWORDS = [
    "just a moment",
    "checking your browser",
    "请稍候",
    "verifying",
    "attention required",
    "one more step",
]

# 硬编码的测试值（与 test_undetected_cookie.py 保持一致）
TEST_URL = "https://0109.cave01-s0in7j02.top/"
TEST_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)
TEST_COOKIES = {
    "cf_clearance": (
        "Fwl79km3SGTKjaCkPhDHnP8YvJEur5rp74wQwgVg8vw-1768456467-1.2.1.1-"
        "kW9LpsecorZ6mAfmxTk1tb4FDshNzdRzYFK5AVJwWGXbT8nb5BFzLmJABzNRIDoeoFSk7rXdVmF96o_obVyoz2WnbJf4w."
        "pMvR7_5DN6mqfTPVp8G8vJqt.P_NsPFwNu7Z9.PYoASHwyq4Ak3Arrg8SLQZM9.u6MjCaYoDnh3FNZh74VM."
        "ZqBlhE1soysoWZS9TWqnM6vHUa1NqKkYdbH0VA0H7YpVLZGiozJs_xYOeeIMh9e2v.wNkmccBTLkzP"
    ),
}


async def main() -> int:
    """主函数：验证 Playwright 是否能使用提供的 cookie 访问网站。"""
    print("=" * 80)
    print(
        "Playwright Cookie 验证测试（基于 test_undetected_cookie.py，仅使用 cf_clearance）"
    )
    print("=" * 80)
    print(f"目标 URL: {TEST_URL}")
    print(f"User-Agent: {TEST_USER_AGENT}")
    print(f"Cookies: {list(TEST_COOKIES.keys())} (仅保留 cf_clearance)")
    print()

    # 1. 提取域名
    parsed = urlparse(TEST_URL)
    domain = parsed.netloc
    print(f"[1/8] 目标域名: {domain}")
    print()

    # 2. 查找本地浏览器路径
    print("[2/8] 查找本地浏览器...")
    browser_path = None
    chromium_paths = [
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for path in chromium_paths:
        if os.path.exists(path):
            browser_path = path
            break

    if browser_path:
        print(f"    使用本地浏览器: {browser_path}")
    else:
        print("    使用 Playwright 自带的 Chromium（未找到本地浏览器）")

    # 3. 启动 Playwright
    print("[3/8] 启动 Playwright...")
    async with async_playwright() as p:
        # 启动浏览器（使用本地 Chromium + 反检测参数）
        launch_args = {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        }
        if browser_path:
            launch_args["executable_path"] = browser_path

        browser = await p.chromium.launch(**launch_args)
        print("    ✓ 浏览器已启动")

        # 4. 创建浏览器上下文（设置 User-Agent + 反检测）
        print("[4/8] 创建浏览器上下文（设置 User-Agent + 反检测）...")
        context = await browser.new_context(
            user_agent=TEST_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # 注入反检测 JS（手工 Stealth）
        await context.add_init_script("""
            // 隐藏 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // 模拟 chrome.runtime（非自动化浏览器有此属性）
            if (!window.chrome) {
                window.chrome = {};
            }
            if (!window.chrome.runtime) {
                window.chrome.runtime = {};
            }

            // 隐藏 Playwright 特有的属性
            delete navigator.__proto__.webdriver;

            // 模拟 plugins（真实浏览器通常有插件）
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ],
            });

            // 模拟 languages（与 User-Agent 匹配）
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en'],
            });

            // 隐藏 permissions 查询的自动化特征
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        print("    ✓ 已注入反检测 JS（手工 Stealth）")

        page = await context.new_page()
        print("    ✓ 上下文已创建")

        # 验证 User-Agent
        actual_ua = await page.evaluate("() => navigator.userAgent")
        if actual_ua == TEST_USER_AGENT:
            print(f"    ✓ User-Agent 匹配: {actual_ua[:50]}...")
        else:
            print("    ⚠ User-Agent 不匹配！")
            print(f"      期望: {TEST_USER_AGENT[:50]}...")
            print(f"      实际: {actual_ua[:50]}...")

        # 5. 导航到目标 URL
        print(f"\n[5/8] 导航到目标 URL: {TEST_URL}")
        await page.goto(TEST_URL, wait_until="domcontentloaded")
        await asyncio.sleep(2)  # 等待页面加载
        print("    ✓ 导航完成")

        # 6. 清除旧 cookies
        print("[6/8] 清除旧 cookies...")
        await context.clear_cookies()
        print("    ✓ 旧 cookies 已清除")

        # 7. 添加新 cookies
        print("[7/8] 添加新 cookies...")
        cookies_to_add = [
            {
                "name": name,
                "value": value,
                "url": TEST_URL,
                "secure": True,
                "httpOnly": False,
            }
            for name, value in TEST_COOKIES.items()
        ]
        await context.add_cookies(cookies_to_add)
        print(f"    ✓ 成功添加 {len(cookies_to_add)} 个 cookies")
        for cookie in cookies_to_add:
            print(f"      - {cookie['name']}")

        # 8. 刷新页面以应用 cookies
        print("\n[8/8] 刷新页面以应用 cookies...")
        await page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(3)  # 等待页面加载
        print("    ✓ 页面刷新完成")

        # 9. 验证 cookies 和页面状态
        print("\n[验证] 检查 cookies 和页面状态...")
        print("=" * 80)

        # 9.1. 读取所有 cookies
        all_cookies = await context.cookies()
        print(f"\n通过 context.cookies() 读取到的 cookies ({len(all_cookies)} 个):")
        # 优先匹配我们添加的 cookie（基于 domain）
        actual_cf = None
        for cookie in all_cookies:
            if cookie["name"] == "cf_clearance":
                cookie_domain = cookie.get("domain", "")
                # 优先匹配我们添加的 domain（精确匹配或带点前缀匹配）
                if cookie_domain == domain or cookie_domain == f".{domain}":
                    actual_cf = cookie["value"]
                    break

        # 如果没找到，回退到字典方式（取第一个）
        if actual_cf is None:
            cookie_dict = {cookie["name"]: cookie["value"] for cookie in all_cookies}
            actual_cf = cookie_dict.get("cf_clearance")

        if actual_cf:
            expected_cf = TEST_COOKIES["cf_clearance"]
            if actual_cf == expected_cf:
                print("    ✓ cf_clearance cookie 值完全匹配")
            else:
                print("    ⚠ cf_clearance cookie 值不匹配！")
                print(f"      期望长度: {len(expected_cf)}")
                print(f"      实际长度: {len(actual_cf)}")
                print(f"      期望前50字符: {expected_cf[:50]}...")
                print(f"      实际前50字符: {actual_cf[:50]}...")
        else:
            print("    ✗ 未找到 cf_clearance cookie！")

        if all_cookies:
            print("\n所有 cookies 详情:")
            for cookie in all_cookies:
                name = cookie.get("name", "unknown")
                cookie_domain = cookie.get("domain", "")
                path = cookie.get("path", "")
                secure = cookie.get("secure", False)
                http_only = cookie.get("httpOnly", False)
                value_preview = (
                    cookie["value"][:30] + "..."
                    if len(cookie["value"]) > 30
                    else cookie["value"]
                )
                print(f"  - {name}:")
                print(f"      domain: {cookie_domain}, path: {path}")
                print(f"      httpOnly: {http_only}, secure: {secure}")
                print(f"      value: {value_preview}")

        # 9.2. 通过 document.cookie 读取（仅非 HttpOnly）
        doc_cookies_str = await page.evaluate("() => document.cookie")
        doc_cookies = {}
        if doc_cookies_str:
            for item in doc_cookies_str.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    doc_cookies[name.strip()] = value.strip()

        print(f"\n通过 document.cookie 读取到的 cookies ({len(doc_cookies)} 个):")
        if doc_cookies:
            for name, value in doc_cookies.items():
                value_preview = value[:30] + "..." if len(value) > 30 else value
                print(f"  - {name}: {value_preview}")
        else:
            print("    (空 - 这是正常的，因为 cf_clearance 通常是 HttpOnly)")

        # 9.3. 检查页面内容
        print("\n页面状态:")
        current_url = page.url
        page_title = await page.title()
        print(f"  当前 URL: {current_url}")
        print(f"  页面标题: {page_title}")

        # 获取页面内容
        page_content = await page.content()
        page_text = await page.inner_text("body")

        # 检查是否包含 Cloudflare 挑战关键词（多维度检查）
        blocked_indicators = []

        # 1. 检查页面标题
        page_title_lower = page_title.lower() if page_title else ""
        for kw in CF_CHALLENGE_KEYWORDS:
            if kw in page_title_lower:
                blocked_indicators.append(f"页面标题包含: {kw}")

        # 2. 检查 URL 中的 Cloudflare challenge token
        url_lower = current_url.lower()
        if "__cf_chl_rt_tk" in url_lower or "__cf_chl_captcha_tk__" in url_lower:
            blocked_indicators.append(
                "URL 包含 Cloudflare challenge token (__cf_chl_rt_tk)"
            )

        # 3. 检查页面文本内容
        page_text_lower = page_text.lower() if page_text else ""
        for kw in CF_CHALLENGE_KEYWORDS:
            if kw in page_text_lower:
                blocked_indicators.append(f"页面内容包含: {kw}")

        # 4. 检查 HTML 内容
        page_content_lower = page_content.lower() if page_content else ""
        for kw in CF_CHALLENGE_KEYWORDS:
            if kw in page_content_lower:
                blocked_indicators.append(f"HTML 内容包含: {kw}")

        # 5. 检查页面标题是否为挑战页
        if (
            "just a moment" in page_title_lower
            or "请稍候" in page_title_lower
            or page_title_lower.startswith("just")
        ):
            blocked_indicators.append(f"页面标题为挑战页: {page_title}")

        still_blocked = len(blocked_indicators) > 0

        print("\n" + "=" * 80)
        print("验证结果")
        print("=" * 80)

        if still_blocked:
            print("❌ 验证失败：页面仍被 Cloudflare 拦截")
            print("\n检测到的拦截指标:")
            for indicator in blocked_indicators:
                print(f"  - {indicator}")
        else:
            print("✅ 验证成功：页面未被 Cloudflare 拦截")

        print("\n页面信息:")
        print(f"  内容长度: {len(page_text)} 字符")
        if page_text:
            preview = page_text[:200].replace("\n", " ")
            print(f"  内容预览: {preview}...")

        print("\n" + "=" * 80)
        if still_blocked:
            print("结论: Playwright 无法使用提供的 cookie 通过 Cloudflare 验证")
        else:
            print("结论: Playwright 成功使用提供的 cookie 通过了 Cloudflare 验证")

        print("\n浏览器窗口将保持打开，请检查页面内容确认结果。")
        print("按回车键关闭浏览器并退出...")
        input()

        await browser.close()
        return 0 if not still_blocked else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
