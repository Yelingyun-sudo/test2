#!/usr/bin/env python3
"""Undetected ChromeDriver Cookie 验证脚本

使用 undetected_chromedriver（与 Docker 容器相同的环境）验证提供的
user_agent 和 cf_clearance cookie 是否能成功访问目标网站。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from urllib.parse import urlparse

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# Cloudflare 挑战页面的关键词（用于检测是否仍被拦截）
CF_CHALLENGE_KEYWORDS = [
    "just a moment",
    "checking your browser",
    "请稍候",
    "verifying",
    "attention required",
    "one more step",
]

# 硬编码的测试值
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


def verify_cookie_with_curl(
    url: str, cookies: dict[str, str], user_agent: str
) -> tuple[bool, str]:
    """用 curl 验证 cookies 是否有效。

    Args:
        url: 目标 URL
        cookies: cookies 字典
        user_agent: 请求使用的 User-Agent

    Returns:
        (is_valid, status_code) - 是否有效和 HTTP 状态码
    """
    # 构建 Cookie header（格式：name1=value1; name2=value2）
    cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())

    cmd = [
        "curl",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-H",
        f"Cookie: {cookie_header}",
        "-H",
        f"User-Agent: {user_agent}",
        url,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        status_code = result.stdout.strip()
        is_valid = status_code == "200"
        return is_valid, status_code
    except Exception as exc:
        return False, f"error: {exc}"


def get_browser_version(browser_path: str) -> int | None:
    """获取浏览器主版本号"""
    try:
        result = subprocess.run(
            [browser_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version_str = result.stdout.strip()
        import re

        match = re.search(r"(\d+)\.", version_str)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def main() -> int:
    """主函数：验证 undetected_chromedriver 是否能使用提供的 cookie 访问网站。"""
    print("=" * 80)
    print("Undetected ChromeDriver Cookie 验证测试（仅使用 cf_clearance）")
    print("=" * 80)
    print(f"目标 URL: {TEST_URL}")
    print(f"User-Agent: {TEST_USER_AGENT}")
    print(f"Cookies: {list(TEST_COOKIES.keys())} (仅保留 cf_clearance)")
    print()

    # 1. 使用 curl 预验证 cookie
    print("[1/8] 使用 curl 预验证 cookie...")
    curl_valid, curl_status = verify_cookie_with_curl(
        TEST_URL, TEST_COOKIES, TEST_USER_AGENT
    )
    if curl_valid:
        print(f"    ✓ curl 验证成功：HTTP {curl_status}")
    else:
        print(f"    ⚠ curl 验证失败：HTTP {curl_status}")
        print("    注意：curl 验证失败，但将继续进行浏览器验证...")

    # 2. 提取域名
    parsed = urlparse(TEST_URL)
    domain = parsed.netloc
    print(f"[2/8] 目标域名: {domain}")
    print()

    # 3. 配置 undetected_chromedriver
    print("[3/8] 配置 undetected_chromedriver...")
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")
    options.add_argument(f"--user-agent={TEST_USER_AGENT}")

    # 优先使用本地 Chromium，其次 Chrome
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
        options.binary_location = browser_path
        browser_version = get_browser_version(browser_path)
        if browser_version:
            print(f"    浏览器版本: {browser_version}")
    else:
        print("    使用默认 Chrome（未找到本地 Chromium/Chrome）")

    # 4. 启动浏览器
    print("[4/8] 启动浏览器...")
    try:
        if browser_path:
            driver = uc.Chrome(
                options=options,
                browser_executable_path=browser_path,
                version_main=browser_version if browser_path else None,
            )
        else:
            driver = uc.Chrome(options=options, version_main=None)
        print("    ✓ 浏览器已启动")
    except Exception as exc:
        print(f"    ✗ 启动浏览器失败: {exc}")
        return 1

    try:
        # 5. 导航到目标 URL
        print(f"[5/8] 导航到目标 URL: {TEST_URL}")
        driver.get(TEST_URL)
        time.sleep(2)  # 等待页面加载
        print("    ✓ 导航完成")

        # 验证 User-Agent
        actual_ua = driver.execute_script("return navigator.userAgent")
        if actual_ua == TEST_USER_AGENT:
            print(f"    ✓ User-Agent 匹配: {actual_ua[:50]}...")
        else:
            print("    ⚠ User-Agent 不匹配！")
            print(f"      期望: {TEST_USER_AGENT[:50]}...")
            print(f"      实际: {actual_ua[:50]}...")

        # 6. 清除旧 cookies
        print("[6/8] 清除旧 cookies...")
        driver.delete_all_cookies()
        print("    ✓ 旧 cookies 已清除")

        # 7. 添加新 cookies
        print("[7/8] 添加新 cookies...")
        for name, value in TEST_COOKIES.items():
            driver.add_cookie(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                }
            )
        print(f"    ✓ 成功添加 {len(TEST_COOKIES)} 个 cookies")
        for name in TEST_COOKIES.keys():
            print(f"      - {name}")

        # 8. 刷新页面以应用 cookies
        print("\n[8/8] 刷新页面以应用 cookies...")
        driver.refresh()
        time.sleep(3)  # 等待页面加载
        print("    ✓ 页面刷新完成")

        # 9. 验证 cookies 和页面状态
        print("\n[验证] 检查 cookies 和页面状态...")
        print("=" * 80)

        # 9.1. 读取所有 cookies
        all_cookies = driver.get_cookies()
        print(f"\n通过 driver.get_cookies() 读取到的 cookies ({len(all_cookies)} 个):")
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
                domain = cookie.get("domain", "")
                path = cookie.get("path", "")
                secure = cookie.get("secure", False)
                http_only = cookie.get("httpOnly", False)
                value_preview = (
                    cookie["value"][:30] + "..."
                    if len(cookie["value"]) > 30
                    else cookie["value"]
                )
                print(f"  - {name}:")
                print(f"      domain: {domain}, path: {path}")
                print(f"      httpOnly: {http_only}, secure: {secure}")
                print(f"      value: {value_preview}")

        # 9.2. 通过 document.cookie 读取（仅非 HttpOnly）
        doc_cookies_str = driver.execute_script("return document.cookie")
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
        current_url = driver.current_url
        page_title = driver.title
        print(f"  当前 URL: {current_url}")
        print(f"  页面标题: {page_title}")

        # 获取页面内容
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()

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
        for kw in CF_CHALLENGE_KEYWORDS:
            if kw in page_text:
                blocked_indicators.append(f"页面内容包含: {kw}")

        # 4. 检查页面标题是否为挑战页
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
            print(
                "结论: Undetected ChromeDriver 无法使用提供的 cookie 通过 Cloudflare 验证"
            )
        else:
            print(
                "结论: Undetected ChromeDriver 成功使用提供的 cookie 通过了 Cloudflare 验证"
            )

        print("\n浏览器窗口将保持打开，请检查页面内容确认结果。")
        print("按回车键关闭浏览器并退出...")
        input()

        return 0 if not still_blocked else 1

    except Exception as exc:
        print(f"\n❌ 执行过程中发生错误: {exc}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
