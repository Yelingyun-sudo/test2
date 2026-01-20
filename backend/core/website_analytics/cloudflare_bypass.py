"""Cloudflare 人机验证绕过工具。

通过 Python 脚本执行绕过，获取 cf_clearance cookie 后注入浏览器。
"""

from __future__ import annotations

import asyncio
import json
import logging
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from agents import Tool, function_tool

if TYPE_CHECKING:
    from website_analytics.playwright_server import AutoSwitchingPlaywrightServer

logger = logging.getLogger(__name__)

# Python 脚本绕过默认超时（秒）
DEFAULT_BYPASS_TIMEOUT = 90

# Cloudflare 挑战页面的关键词（用于检测是否仍被拦截）
CF_CHALLENGE_KEYWORDS = [
    "just a moment",
    "checking your browser",
    "请稍候",
    "verifying",
    "attention required",
    "one more step",
]


def _extract_base_url(url: str) -> str:
    """从 URL 中提取协议+域名部分（去除路径和 hash）。

    Args:
        url: 完整 URL

    Returns:
        base_url，格式为 "scheme://netloc/"

    Examples:
        "https://www.en-guide.top/#/login" -> "https://www.en-guide.top/"
        "http://ouucloud.top/register?id=123" -> "http://ouucloud.top/"
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


async def _verify_cookie_with_curl(
    url: str, cf_clearance: str, user_agent: str
) -> tuple[bool, str]:
    """用 curl 验证 cf_clearance cookie 是否有效。

    Args:
        url: 目标 URL
        cf_clearance: Cloudflare clearance cookie 值
        user_agent: 请求使用的 User-Agent

    Returns:
        (is_valid, status_code) - 是否有效和 HTTP 状态码
    """
    cmd = [
        "curl",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-H",
        f"Cookie: cf_clearance={cf_clearance}",
        "-H",
        f"User-Agent: {user_agent}",
        url,
    ]

    logger.debug("[调试] curl 验证命令：%s", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        status_code = stdout.decode().strip()
        is_valid = status_code == "200"

        logger.info(
            "[调试] curl 验证结果：status_code=%s, %s",
            status_code,
            "有效" if is_valid else "无效",
        )
        return is_valid, status_code

    except Exception as exc:
        logger.warning("[调试] curl 验证失败：%s", exc)
        return False, f"error: {exc}"


async def _inject_stealth_script(
    playwright_server: "AutoSwitchingPlaywrightServer",
) -> bool:
    """注入反检测 JavaScript 代码。

    Args:
        playwright_server: Playwright MCP 服务器实例

    Returns:
        是否注入成功
    """
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
        logger.info("反检测 JS 注入成功")
        return True
    except Exception as exc:
        logger.warning("反检测 JS 注入失败：%s", exc)
        return False


async def _run_python_bypass(url: str, timeout: int = DEFAULT_BYPASS_TIMEOUT) -> dict:
    """调用 Python 脚本执行 Cloudflare 绕过。

    Args:
        url: 需要绕过验证的目标 URL
        timeout: 脚本执行超时（秒）

    Returns:
        脚本返回的 JSON 结果，包含 success、cf_clearance、user_agent 等字段
    """
    # 获取脚本的绝对路径
    script_path = (
        Path(__file__).parent.parent.parent
        / "external"
        / "cloudflare-bypass"
        / "bypass_cloudflare_docker.py"
    )

    cmd = [
        "uv",
        "run",
        "python",
        str(script_path),
        url,
        "--output-json",
        "--max-wait",
        "60",
        "--browser",
        "chrome",  # 使用 Google Chrome 而非 Chromium
    ]

    logger.info("正在调用 Python 脚本绕过 Cloudflare：%s", url)
    logger.debug("脚本命令：%s", " ".join(cmd))

    # 用于在异常处理中访问
    stdout_text = ""
    stderr_text = ""
    exit_code = -1

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        # 解码输出
        stdout_text = stdout.decode("utf-8", errors="ignore").strip()
        stderr_text = stderr.decode("utf-8", errors="ignore").strip()
        exit_code = proc.returncode

        if exit_code != 0:
            logger.warning("脚本进程返回非零退出码 %d：%s", exit_code, stderr_text)
            # 即使退出码非零，也尝试解析 stdout（可能包含有效的 JSON 结果）

        # stdout 为空时返回完整诊断信息
        if not stdout_text:
            return {
                "success": False,
                "error": f"脚本输出为空，退出码：{exit_code}",
                "exit_code": exit_code,
                "stdout": "",
                "stderr": stderr_text,
            }

        result = json.loads(stdout_text)

        # 附加诊断信息（即使成功也包含）
        if stderr_text:
            result["_stderr"] = stderr_text
        result["_exit_code"] = exit_code

        logger.info(
            "Python 脚本绕过结果：success=%s, duration=%.2fs",
            result.get("success"),
            result.get("duration", 0),
        )
        return result

    except asyncio.TimeoutError:
        logger.error("脚本执行超时（%d 秒）", timeout)
        return {
            "success": False,
            "error": f"脚本执行超时（{timeout} 秒）",
            "exit_code": exit_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
    except json.JSONDecodeError as exc:
        logger.error("脚本输出不是有效的 JSON：%s", exc)
        return {
            "success": False,
            "error": f"脚本输出解析失败：{exc}",
            "exit_code": exit_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
    except FileNotFoundError:
        logger.error("uv 或 python 未安装或不在 PATH 中")
        return {
            "success": False,
            "error": "uv 或 python 未安装或不在 PATH 中",
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
        }
    except Exception as exc:
        logger.error("脚本调用失败：%s: %s", type(exc).__name__, exc)
        return {
            "success": False,
            "error": f"脚本调用失败：{type(exc).__name__}: {exc}",
            "exit_code": exit_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }


def build_bypass_cloudflare_tool(
    playwright_server: "AutoSwitchingPlaywrightServer",
) -> Tool:
    """创建 Cloudflare 人机验证绕过工具。

    通过 Python 脚本执行绕过，获取 cf_clearance cookie 后注入 Playwright 浏览器。

    Args:
        playwright_server: Playwright MCP 服务器实例

    Returns:
        工具声明
    """

    @function_tool(
        name_override="bypass_cloudflare",
        description_override=(
            "绕过 Cloudflare 人机验证。"
            "检测到 Cloudflare 挑战页（Just a moment/请稍候）时调用此工具。"
            "工具会自动获取 cf_clearance cookie 并注入浏览器，然后刷新页面。"
        ),
    )
    async def bypass_cloudflare(url: str) -> str:
        """绕过 Cloudflare 人机验证。

        Args:
            url: 需要绕过验证的目标 URL

        Returns:
            JSON 字符串，包含 success、cf_clearance、user_agent、message 等字段
        """
        # 1. 调用 Python 脚本获取 cookie
        result = await _run_python_bypass(url)

        # [调试] 打印完整的脚本返回结果
        logger.warning(
            "[调试] 脚本完整返回结果: %s",
            json.dumps(result, ensure_ascii=False, indent=2),
        )

        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            stderr_info = result.get("stderr", "")
            stdout_info = result.get("stdout", "")
            exit_code = result.get("exit_code", -1)

            # 构建详细错误信息
            detail = f"脚本绕过失败：{error_msg}"
            if stderr_info:
                detail += f"\n[stderr]\n{stderr_info}"
            if stdout_info:
                detail += f"\n[stdout]\n{stdout_info}"

            logger.warning("脚本绕过失败：%s", error_msg)
            logger.debug("stderr: %s", stderr_info)
            logger.debug("stdout: %s", stdout_info)

            return json.dumps(
                {
                    "success": False,
                    "message": detail,
                    "exit_code": exit_code,
                },
                ensure_ascii=False,
            )

        cf_clearance = result.get("cf_clearance")

        if not cf_clearance:
            logger.warning("脚本返回成功但未获取到 cf_clearance cookie")
            return json.dumps(
                {
                    "success": False,
                    "message": "未获取到 cf_clearance cookie",
                },
                ensure_ascii=False,
            )

        # 提取 URL：优先使用脚本返回的 final_url
        original_url = url
        final_url = result.get("final_url") or original_url
        base_url = _extract_base_url(final_url)

        logger.info(
            "[调试] 脚本绕过成功：cf_clearance=%s...",
            cf_clearance[:20] if len(cf_clearance) > 20 else cf_clearance,
        )
        logger.info(
            "URL 信息 - 原始: %s, 最终: %s, Base: %s",
            original_url,
            final_url,
            base_url,
        )

        # 2. [调试] 用 curl 验证 cookie 是否有效
        curl_valid, curl_status = await _verify_cookie_with_curl(
            base_url, cf_clearance, result.get("user_agent", "")
        )
        if not curl_valid:
            logger.warning(
                "[调试] curl 验证失败（status=%s），cookie 可能无效",
                curl_status,
            )

        # 3. 提取域名（用于兜底方案）
        parsed = urlparse(final_url)
        domain = parsed.netloc
        logger.debug("目标域名：%s", domain)

        # 4. 注入反检测 JS
        await _inject_stealth_script(playwright_server)

        # 5. 导航到最终 URL
        try:
            logger.debug("导航到最终 URL：%s", final_url)
            await playwright_server.call_tool(
                "browser_navigate",
                {"url": final_url},
            )
            logger.info("导航完成")

            # 等待页面加载
            try:
                await playwright_server.call_tool("browser_wait_for", {"time": 2})
            except Exception:
                await asyncio.sleep(2)
        except Exception as exc:
            logger.error("导航失败：%s", exc)
            return json.dumps(
                {
                    "success": False,
                    "message": f"导航失败：{exc}",
                },
                ensure_ascii=False,
            )

        # 6. 清除旧 cookies
        try:
            await playwright_server.call_tool("browser_clear_cookies", {})
            logger.info("成功清除旧 cookies")
        except Exception:
            try:
                await playwright_server.call_tool("clear_cookies", {})
                logger.info("成功清除旧 cookies（使用 clear_cookies）")
            except Exception as exc:
                logger.warning("清除 cookies 失败：%s", exc)
                logger.warning("将继续进行，但可能残留旧 cookies")

        # 7. 添加新 cookies（使用 url 参数，参考测试程序）
        all_cookies_dict = result.get("cookies", {})
        if not all_cookies_dict and cf_clearance:
            all_cookies_dict = {"cf_clearance": cf_clearance}

        cookies_to_add = [
            {
                "name": name,
                "value": value,
                "url": base_url,  # 使用 base_url（仅协议+域名）
                "path": "/",
                "secure": True,
                "httpOnly": False,
            }
            for name, value in all_cookies_dict.items()
        ]

        cookies_added_via_api = False
        try:
            await playwright_server.call_tool(
                "browser_add_cookies",
                {"cookies": cookies_to_add},
            )
            logger.info(
                "成功添加 %d 个 cookies（使用 browser_add_cookies, base_url=%s）: %s",
                len(cookies_to_add),
                base_url,
                list(all_cookies_dict.keys()),
            )
            cookies_added_via_api = True
        except Exception:
            try:
                await playwright_server.call_tool(
                    "add_cookies",
                    {"cookies": cookies_to_add},
                )
                logger.info(
                    "成功添加 %d 个 cookies（使用 add_cookies, base_url=%s）: %s",
                    len(cookies_to_add),
                    base_url,
                    list(all_cookies_dict.keys()),
                )
                cookies_added_via_api = True
            except Exception as exc:
                logger.warning("MCP API 添加 cookies 失败：%s", exc)
                logger.info("将尝试使用 browser_evaluate 作为兜底方案")

        # 8. 兜底方案：通过 browser_evaluate 直接设置 cookie
        cookie_script = f"""
        () => {{
            document.cookie = "cf_clearance={cf_clearance}; domain=.{domain}; path=/; secure";
            return document.cookie;
        }}
        """
        try:
            logger.debug("执行兜底方案设置 cookie...")
            await playwright_server.call_tool(
                "browser_evaluate",
                {"function": cookie_script},
            )
            if not cookies_added_via_api:
                logger.info("通过 browser_evaluate 设置 cookie 成功")
            else:
                logger.debug("兜底方案执行成功")
        except Exception as exc:
            if not cookies_added_via_api:
                logger.error("兜底方案也失败：%s", exc)
                return json.dumps(
                    {
                        "success": False,
                        "message": f"Cookie 设置失败：{exc}",
                    },
                    ensure_ascii=False,
                )
            else:
                logger.warning("兜底方案失败（不影响主流程）：%s", exc)

        # 9. 刷新页面以应用 cookies
        try:
            logger.debug("刷新页面以应用 cookies（访问 final_url）...")
            await playwright_server.call_tool(
                "browser_navigate",
                {"url": final_url},
            )
            logger.info("页面刷新完成")

            # 等待页面加载
            try:
                await playwright_server.call_tool("browser_wait_for", {"time": 3})
            except Exception:
                await asyncio.sleep(3)
        except Exception as exc:
            logger.error("刷新页面失败：%s", exc)
            return json.dumps(
                {
                    "success": False,
                    "message": f"刷新页面失败：{exc}",
                },
                ensure_ascii=False,
            )

        # 10. 验证是否绕过成功
        try:
            snapshot_result = await playwright_server.call_tool(
                "browser_snapshot",
                {},
            )
            snapshot_text = snapshot_result.content[0].text.lower()

            # 检查是否还在 Cloudflare 挑战页
            still_blocked = any(kw in snapshot_text for kw in CF_CHALLENGE_KEYWORDS)

            if still_blocked:
                logger.warning("Cookie 注入后仍被 Cloudflare 拦截")
                return json.dumps(
                    {
                        "success": False,
                        "message": "Cookie 注入后仍被 Cloudflare 拦截（可能 UA 不匹配）",
                    },
                    ensure_ascii=False,
                )

        except Exception as exc:
            logger.warning("验证绕过状态失败：%s", exc)
            # 验证失败时假设成功，让 Agent 继续执行

        logger.info("Cloudflare 验证绕过成功")
        return json.dumps(
            {
                "success": True,
                "cf_clearance": cf_clearance,
                "user_agent": result.get("user_agent", ""),
                "message": "Cloudflare 验证已绕过",
                "duration": result.get("duration", 0),
            },
            ensure_ascii=False,
        )

    return bypass_cloudflare


__all__ = ["build_bypass_cloudflare_tool"]
