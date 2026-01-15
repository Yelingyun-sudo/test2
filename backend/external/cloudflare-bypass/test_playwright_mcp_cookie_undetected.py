#!/usr/bin/env python3
"""Playwright MCP Cookie 验证脚本（基于 test_playwright_cookie_undetected.py）

使用 Playwright MCP API（与 test_playwright_cookie_undetected.py 相同的测试值和验证逻辑）
验证提供的 user_agent 和 cf_clearance cookie 是否能成功访问目标网站。
使用 Playwright MCP Server 而不是直接的 Playwright API。
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from website_analytics.playwright_server import AutoSwitchingPlaywrightServer
from website_analytics.utils import build_playwright_args

# Cloudflare 挑战页面的关键词（用于检测是否仍被拦截）
CF_CHALLENGE_KEYWORDS = [
    "just a moment",
    "checking your browser",
    "请稍候",
    "verifying",
    "attention required",
    "one more step",
]

# 硬编码的测试值（与 test_playwright_cookie_undetected.py 保持一致）
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


def _clean_browser_evaluate_result(text: str) -> str:
    """清理 browser_evaluate 返回的文本。

    处理格式：
    - ### Result\n"value"
    - ### Ran Playwright code\n...\n### Result\n"value"
    - 包含执行日志的完整输出

    参考 cloudflare_bypass.py 和 tools.py 中的实现。

    Args:
        text: browser_evaluate 返回的原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    # 优先用正则提取 UA 主体（如果是 User-Agent）
    match = re.search(r"Mozilla/5\.0.*?Safari/[\d.]+", text)
    if match:
        return match.group(0)

    # 提取 ### Result 部分（如果存在）
    if "### Result" in text:
        # 找到 ### Result 后面的内容
        parts = text.split("### Result")
        if len(parts) > 1:
            result_part = parts[-1].strip()
            # 移除开头的换行
            if result_part.startswith("\n"):
                result_part = result_part[1:]
            text = result_part

    # 迭代清理所有可能的包装字符（最多 5 层）
    cleaned = text
    for _ in range(5):
        old = cleaned
        # 移除前缀
        if cleaned.startswith("### Result\n"):
            cleaned = cleaned[12:]  # len("### Result\n") = 12
        elif cleaned.startswith("### Result"):
            cleaned = cleaned[10:]  # len("### Result") = 10
        # 移除包装字符
        cleaned = cleaned.strip().strip('"').strip("'").strip("`").strip()
        if old == cleaned:
            break  # 没有变化，停止循环

    return cleaned


def _parse_snapshot_text(snapshot_text: str) -> dict[str, str]:
    """从 browser_snapshot 返回的文本中解析页面信息。

    Args:
        snapshot_text: browser_snapshot 返回的文本内容

    Returns:
        包含 url, title, content 的字典
    """
    result = {"url": "", "title": "", "content": ""}

    # 尝试解析 URL（通常在快照的开头或特定位置）
    url_match = re.search(r"URL:\s*(https?://[^\s]+)", snapshot_text)
    if url_match:
        result["url"] = url_match.group(1)
    else:
        # 尝试从其他格式解析
        url_match = re.search(r"Location:\s*(https?://[^\s]+)", snapshot_text)
        if url_match:
            result["url"] = url_match.group(1)

    # 尝试解析标题
    title_match = re.search(r"Title:\s*([^\n]+)", snapshot_text)
    if title_match:
        result["title"] = title_match.group(1).strip()
    else:
        # 尝试从 HTML 标签解析
        title_match = re.search(
            r"<title[^>]*>([^<]+)</title>", snapshot_text, re.IGNORECASE
        )
        if title_match:
            result["title"] = title_match.group(1).strip()

    # 内容就是整个快照文本（去除标题和 URL 部分）
    result["content"] = snapshot_text

    return result


async def main() -> int:
    """主函数：验证 Playwright MCP 是否能使用提供的 cookie 访问网站。"""
    print("=" * 80)
    print(
        "Playwright MCP Cookie 验证测试（基于 test_playwright_cookie_undetected.py，仅使用 cf_clearance）"
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

    # 2. 创建临时输出目录
    print("[2/8] 创建临时输出目录...")
    output_dir = Path(tempfile.mkdtemp(prefix="playwright_mcp_test_"))
    print(f"    输出目录: {output_dir}")

    # 3. 构建 Playwright 参数
    print("[3/8] 构建 Playwright MCP 参数...")
    playwright_args = build_playwright_args(
        output_dir=output_dir,
        headless=False,
        user_agent=TEST_USER_AGENT,
    )
    playwright_params = {
        "command": "npx",
        "args": playwright_args,
    }
    print("    ✓ 参数构建完成")

    # 4. 启动 Playwright MCP Server
    print("[4/8] 启动 Playwright MCP Server...")
    async with AutoSwitchingPlaywrightServer(
        name="playwright-mcp",
        params=playwright_params,
        client_session_timeout_seconds=120,
    ) as playwright_server:
        print("    ✓ MCP Server 已启动")

        # 5. 设置 User-Agent
        print("[5/8] 设置 User-Agent...")
        try:
            await playwright_server.call_tool(
                "browser_set_user_agent",
                {"user_agent": TEST_USER_AGENT},
            )
            print(f"    ✓ User-Agent 已设置: {TEST_USER_AGENT[:50]}...")
        except Exception:
            try:
                await playwright_server.call_tool(
                    "set_user_agent",
                    {"user_agent": TEST_USER_AGENT},
                )
                print(
                    f"    ✓ User-Agent 已设置（使用 set_user_agent）: {TEST_USER_AGENT[:50]}..."
                )
            except Exception as exc:
                print(f"    ⚠ 设置 User-Agent 失败: {exc}")
                print("    注意：将继续进行，但 User-Agent 可能不匹配")

        # [诊断] 尝试注入反检测 JS（参考成功版本）
        print("\n[诊断] 尝试注入反检测 JS...")
        stealth_script = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        if (!window.chrome) {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {};
        }
        delete navigator.__proto__.webdriver;
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
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en-US', 'en'],
        });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        return 'Stealth script injected';
        """
        try:
            await playwright_server.call_tool(
                "browser_evaluate",
                {"function": f"() => {{ {stealth_script} }}"},
            )
            print("    ✓ 反检测 JS 注入成功")
        except Exception as exc:
            print(f"    ⚠ 反检测 JS 注入失败: {exc}")
            print("    注意：将继续进行，但可能被 Cloudflare 检测")

        # 6. 导航到目标 URL（按照成功版本的顺序）
        print(f"\n[6/8] 导航到目标 URL: {TEST_URL}")
        try:
            await playwright_server.call_tool(
                "browser_navigate",
                {"url": TEST_URL},
            )
            print("    ✓ 导航完成")

            # 等待页面加载
            try:
                await playwright_server.call_tool("browser_wait_for", {"time": 2})
            except Exception:
                await asyncio.sleep(2)
        except Exception as exc:
            print(f"    ✗ 导航失败: {exc}")
            return 1

        # 7. 清除旧 cookies（按照成功版本的顺序）
        print("[7/8] 清除旧 cookies...")
        try:
            await playwright_server.call_tool("browser_clear_cookies", {})
            print("    ✓ 旧 cookies 已清除")
        except Exception:
            try:
                await playwright_server.call_tool("clear_cookies", {})
                print("    ✓ 旧 cookies 已清除（使用 clear_cookies）")
            except Exception as exc:
                print(f"    ⚠ 清除 cookies 失败: {exc}")
                print("    注意：将继续进行，但可能残留旧 cookies")

        # 8. 添加新 cookies（按照成功版本的顺序，使用 url 方式）
        print("[8/8] 添加新 cookies...")
        cookies_to_add = [
            {
                "name": name,
                "value": value,
                "url": TEST_URL,  # 使用 url，与成功版本一致
                "path": "/",
                "secure": True,
                "httpOnly": False,
            }
            for name, value in TEST_COOKIES.items()
        ]

        cookies_added_via_api = False
        try:
            await playwright_server.call_tool(
                "browser_add_cookies",
                {"cookies": cookies_to_add},
            )
            print(
                f"    ✓ 成功添加 {len(cookies_to_add)} 个 cookies（使用 browser_add_cookies）"
            )
            for cookie in cookies_to_add:
                print(f"      - {cookie['name']}")
            cookies_added_via_api = True
        except Exception as exc1:
            try:
                await playwright_server.call_tool(
                    "add_cookies",
                    {"cookies": cookies_to_add},
                )
                print(
                    f"    ✓ 成功添加 {len(cookies_to_add)} 个 cookies（使用 add_cookies）"
                )
                for cookie in cookies_to_add:
                    print(f"      - {cookie['name']}")
                cookies_added_via_api = True
            except Exception as exc2:
                print("    ⚠ MCP API 添加 cookies 失败:")
                print(f"      - browser_add_cookies: {exc1}")
                print(f"      - add_cookies: {exc2}")
                print("    将尝试使用 browser_evaluate 作为兜底方案...")

        # [诊断] 兜底方案：通过 browser_evaluate 直接设置 cookie
        if not cookies_added_via_api:
            print("\n[诊断] 使用 browser_evaluate 兜底方案设置 cookie...")
            cf_clearance_value = TEST_COOKIES["cf_clearance"]
            cookie_script = f"""
            () => {{
                document.cookie = "cf_clearance={cf_clearance_value}; domain=.{domain}; path=/; secure";
                return document.cookie;
            }}
            """
            try:
                await playwright_server.call_tool(
                    "browser_evaluate",
                    {"function": cookie_script},
                )
                print("    ✓ 通过 browser_evaluate 设置 cookie 成功")
            except Exception as exc:
                print(f"    ✗ 兜底方案也失败: {exc}")
                return 1
        else:
            # 即使 API 成功，也尝试兜底方案确保设置成功
            print("\n[诊断] 添加兜底方案确保 cookie 设置成功...")
            cf_clearance_value = TEST_COOKIES["cf_clearance"]
            cookie_script = f"""
            () => {{
                document.cookie = "cf_clearance={cf_clearance_value}; domain=.{domain}; path=/; secure";
                return document.cookie;
            }}
            """
            try:
                await playwright_server.call_tool(
                    "browser_evaluate",
                    {"function": cookie_script},
                )
                print("    ✓ 兜底方案执行成功")
            except Exception as exc:
                print(f"    ⚠ 兜底方案失败（不影响主流程）: {exc}")

        # [诊断] 验证 cookies 是否真的被设置（添加后立即验证）
        print("\n[诊断] 验证 cookies 是否真的被设置（添加后）...")
        cookie_check_script = """
        () => {
            const cookies = document.cookie.split(';');
            const result = {
                documentCookie: document.cookie,
                cookies: {},
                hasCfClearance: false,
                cfClearanceValue: null
            };
            for (let cookie of cookies) {
                const trimmed = cookie.trim();
                if (trimmed) {
                    const [name, value] = trimmed.split('=');
                    if (name) {
                        result.cookies[name.trim()] = value || '';
                        if (name.trim() === 'cf_clearance') {
                            result.hasCfClearance = true;
                            result.cfClearanceValue = value || '';
                        }
                    }
                }
            }
            return JSON.stringify(result);
        }
        """
        try:
            check_result = await playwright_server.call_tool(
                "browser_evaluate",
                {"function": cookie_check_script},
            )
            check_result_raw = ""
            if check_result.content:
                for item in check_result.content:
                    if hasattr(item, "text"):
                        check_result_raw += item.text
                    elif isinstance(item, str):
                        check_result_raw += item
            check_result_cleaned = _clean_browser_evaluate_result(check_result_raw)
            print(f"    验证结果: {check_result_cleaned[:200]}...")

            # 尝试解析 JSON
            try:
                # 移除可能的引号包装
                json_str = check_result_cleaned.strip().strip('"').strip("'").strip("`")
                cookie_info = json.loads(json_str)
                if cookie_info.get("hasCfClearance"):
                    actual_cf = cookie_info.get("cfClearanceValue", "")
                    expected_cf = TEST_COOKIES["cf_clearance"]
                    if actual_cf == expected_cf:
                        print("    ✓ cf_clearance cookie 值完全匹配")
                    else:
                        print("    ⚠ cf_clearance cookie 值不匹配！")
                        print(f"      期望前50字符: {expected_cf[:50]}...")
                        print(
                            f"      实际前50字符: {actual_cf[:50] if actual_cf else 'None'}..."
                        )
                else:
                    print("    ⚠ 未找到 cf_clearance cookie（可能是 HttpOnly）")
                    print(
                        f"    document.cookie: {cookie_info.get('documentCookie', '')[:100]}..."
                    )
            except Exception as json_exc:
                print(f"    ⚠ 无法解析验证结果 JSON: {json_exc}")
                print(f"    原始结果: {check_result_cleaned[:200]}...")
        except Exception as exc:
            print(f"    ⚠ 验证 cookies 失败: {exc}")

        # 9. 刷新页面以应用 cookies
        print("\n刷新页面以应用 cookies...")
        try:
            await playwright_server.call_tool(
                "browser_navigate",
                {"url": TEST_URL},
            )
            print("    ✓ 页面刷新完成")

            # 等待页面加载
            try:
                await playwright_server.call_tool("browser_wait_for", {"time": 3})
            except Exception:
                await asyncio.sleep(3)
        except Exception as exc:
            print(f"    ✗ 刷新页面失败: {exc}")
            return 1

        # [诊断] 验证 User-Agent（刷新后）
        print("\n[诊断] 验证 User-Agent（刷新后）...")
        try:
            ua_result = await playwright_server.call_tool(
                "browser_evaluate",
                {"function": "() => navigator.userAgent"},
            )
            actual_ua_raw = ""
            if ua_result.content:
                for item in ua_result.content:
                    if hasattr(item, "text"):
                        actual_ua_raw += item.text
                    elif isinstance(item, str):
                        actual_ua_raw += item
            # 使用清理函数处理返回的文本
            actual_ua = _clean_browser_evaluate_result(actual_ua_raw)
            print(f"    实际 User-Agent: {actual_ua[:80]}...")
            if actual_ua == TEST_USER_AGENT:
                print("    ✓ User-Agent 完全匹配")
            else:
                print("    ⚠ User-Agent 不匹配！")
                print(f"      期望: {TEST_USER_AGENT[:80]}...")
                print(f"      实际: {actual_ua[:80]}...")
                print(f"      原始: {actual_ua_raw[:100]}...")
        except Exception as exc:
            print(f"    ⚠ 无法获取 User-Agent: {exc}")

        # [诊断] 验证 Cookies（刷新后）
        print("\n[诊断] 验证 Cookies（刷新后）...")
        cookie_check_script_refresh = """
        () => {
            const cookies = document.cookie.split(';');
            const result = {
                documentCookie: document.cookie,
                cookies: {},
                hasCfClearance: false,
                cfClearanceValue: null
            };
            for (let cookie of cookies) {
                const trimmed = cookie.trim();
                if (trimmed) {
                    const [name, value] = trimmed.split('=');
                    if (name) {
                        result.cookies[name.trim()] = value || '';
                        if (name.trim() === 'cf_clearance') {
                            result.hasCfClearance = true;
                            result.cfClearanceValue = value || '';
                        }
                    }
                }
            }
            return JSON.stringify(result);
        }
        """
        try:
            check_result_refresh = await playwright_server.call_tool(
                "browser_evaluate",
                {"function": cookie_check_script_refresh},
            )
            check_result_refresh_raw = ""
            if check_result_refresh.content:
                for item in check_result_refresh.content:
                    if hasattr(item, "text"):
                        check_result_refresh_raw += item.text
                    elif isinstance(item, str):
                        check_result_refresh_raw += item
            check_result_refresh_cleaned = _clean_browser_evaluate_result(
                check_result_refresh_raw
            )
            print(f"    验证结果: {check_result_refresh_cleaned[:200]}...")

            # 尝试解析 JSON
            try:
                json_str = (
                    check_result_refresh_cleaned.strip()
                    .strip('"')
                    .strip("'")
                    .strip("`")
                )
                cookie_info_refresh = json.loads(json_str)
                if cookie_info_refresh.get("hasCfClearance"):
                    actual_cf_refresh = cookie_info_refresh.get("cfClearanceValue", "")
                    expected_cf = TEST_COOKIES["cf_clearance"]
                    if actual_cf_refresh == expected_cf:
                        print("    ✓ cf_clearance cookie 值完全匹配")
                    else:
                        print("    ⚠ cf_clearance cookie 值不匹配！")
                        print(f"      期望前50字符: {expected_cf[:50]}...")
                        print(
                            f"      实际前50字符: {actual_cf_refresh[:50] if actual_cf_refresh else 'None'}..."
                        )
                else:
                    print("    ⚠ 未找到 cf_clearance cookie（可能是 HttpOnly）")
                    print(
                        f"    document.cookie: {cookie_info_refresh.get('documentCookie', '')[:100]}..."
                    )
                    print(
                        f"    所有 cookies: {list(cookie_info_refresh.get('cookies', {}).keys())}"
                    )
            except Exception as json_exc:
                print(f"    ⚠ 无法解析验证结果 JSON: {json_exc}")
                print(f"    原始结果: {check_result_refresh_cleaned[:200]}...")
        except Exception as exc:
            print(f"    ⚠ 验证 cookies 失败: {exc}")

        # 验证 cookies 和页面状态
        print("\n[验证] 检查 cookies 和页面状态...")
        print("=" * 80)

        # 获取页面快照
        print("\n获取页面快照...")
        try:
            snapshot_result = await playwright_server.call_tool("browser_snapshot", {})
            snapshot_text = ""
            if snapshot_result.content:
                for item in snapshot_result.content:
                    if hasattr(item, "text"):
                        snapshot_text += item.text
                    elif isinstance(item, str):
                        snapshot_text += item

            if not snapshot_text:
                print("    ⚠ 无法获取页面快照内容")
                snapshot_text = ""
        except Exception as exc:
            print(f"    ⚠ 获取页面快照失败: {exc}")
            snapshot_text = ""

        # 解析页面信息
        page_info = _parse_snapshot_text(snapshot_text)
        current_url = page_info.get("url", TEST_URL)
        page_title = page_info.get("title", "")
        page_content = page_info.get("content", "")
        page_text_lower = page_content.lower() if page_content else ""

        print("\n页面状态:")
        print(f"  当前 URL: {current_url}")
        print(f"  页面标题: {page_title}")

        # 尝试获取 cookies（如果 MCP 支持）
        print("\n尝试获取 cookies...")
        actual_cf = None

        # MCP 可能没有直接获取 cookies 的工具，我们通过页面内容验证
        # 但先尝试是否有相关工具
        try:
            # 尝试通过 browser_snapshot 或其他方式获取 cookies
            # 注意：Playwright MCP 可能不支持直接获取 cookies
            # 这里我们主要依赖页面内容验证
            pass
        except Exception:
            pass

        # 由于 MCP 可能不支持直接获取 cookies，我们通过页面内容验证
        # 检查页面是否包含我们期望的内容（表示通过了 Cloudflare 验证）
        print("    注意：MCP API 可能不支持直接获取 cookies，将通过页面内容验证")

        # 检查页面内容
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
        print(f"  内容长度: {len(page_content)} 字符")
        if page_content:
            # 提取文本预览（去除 HTML 标签）
            text_preview = re.sub(r"<[^>]+>", "", page_content[:500])
            preview = text_preview[:200].replace("\n", " ")
            print(f"  内容预览: {preview}...")

        print("\n" + "=" * 80)
        if still_blocked:
            print("结论: Playwright MCP 无法使用提供的 cookie 通过 Cloudflare 验证")
        else:
            print("结论: Playwright MCP 成功使用提供的 cookie 通过了 Cloudflare 验证")

        print("\n浏览器窗口将保持打开，请检查页面内容确认结果。")
        print("按回车键关闭浏览器并退出...")
        input()

        return 0 if not still_blocked else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
