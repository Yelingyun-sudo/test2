"""探测邮箱账号 IMAP 连接有效性并统计邮件数量。

此脚本用于检查 backend/email_accounts.yaml 中配置的邮箱账号是否可用：
1. 连接 IMAP 服务器
2. 测试登录
3. 统计邮件数量（总邮件数和未读邮件数）

支持探测所有账号或指定特定账号。
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path
from typing import Any

import aioimaplib

# 添加 core 目录到 Python 路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from website_analytics.email_accounts import get_account_manager  # noqa: E402
from website_analytics.models import EmailAccount  # noqa: E402


async def check_account(account: EmailAccount, verbose: bool = False) -> dict[str, Any]:
    """探测单个邮箱账号的连接有效性。

    Args:
        account: 邮箱账号配置
        verbose: 是否输出详细信息

    Returns:
        探测结果字典，包含成功状态、邮件统计、错误信息等
    """
    result = {
        "email": account.register_account,
        "success": False,
        "imap_server": account.imap_server,
        "imap_port": account.imap_port,
        "total_emails": None,
        "unseen_emails": None,
        "error": None,
        "elapsed_time": 0.0,
    }

    start_time = time.time()
    imap_client = None

    try:
        if verbose:
            print(f"\n[{account.register_account}]")
            print(f"  → 连接 {account.imap_server}:{account.imap_port}...")

        # 1. 连接 IMAP 服务器
        imap_client = aioimaplib.IMAP4_SSL(
            host=account.imap_server,
            port=account.imap_port,
            timeout=30,
        )
        await imap_client.wait_hello_from_server()

        if verbose:
            print(f"  → 登录用户: {account.imap_username}")

        # 2. 登录
        login_response = await imap_client.login(
            account.imap_username,
            account.imap_password,
        )

        if login_response.result != "OK":
            error_msg = (
                login_response.lines[0].decode("utf-8", errors="ignore")
                if login_response.lines
                else "登录失败"
            )
            result["error"] = f"登录失败: {error_msg}"
            result["elapsed_time"] = time.time() - start_time
            return result

        # 发送 ID 命令（RFC 2971）提供客户端标识，避免被识别为不安全登录
        # 注意：必须在 LOGIN 之后、SELECT 之前调用，这是 163 邮箱的要求
        try:
            await imap_client.id(
                name="Website Analytics",
                version="1.0",
            )
            if verbose:
                print("  → 已发送 ID 命令")
        except Exception:
            # ID 命令失败不影响后续流程
            if verbose:
                print("  → ID 命令失败（忽略）")

        if verbose:
            print("  → 选择 INBOX 邮箱...")

        # 3. 选择 INBOX 邮箱
        select_response = await imap_client.select("INBOX")

        if verbose:
            print(f"  → SELECT 响应: {select_response.result}")
            if select_response.lines:
                try:
                    detail = select_response.lines[0].decode("utf-8", errors="ignore")
                    print(f"  → 详细信息: {detail[:100]}")
                except (IndexError, AttributeError):
                    pass

        if select_response.result != "OK":
            # 提取详细错误信息
            error_detail = "未知错误"
            if select_response.lines:
                try:
                    error_detail = select_response.lines[0].decode("utf-8", errors="ignore")
                except (IndexError, AttributeError):
                    error_detail = str(select_response.lines)

            result["error"] = f"无法选择 INBOX 邮箱: {error_detail}"
            result["elapsed_time"] = time.time() - start_time
            return result

        if verbose:
            print("  → 统计邮件数量...")

        # 4. 解析总邮件数（从 SELECT 响应中提取 EXISTS）
        total_emails = 0
        for line in select_response.lines:
            line_str = line.decode("utf-8", errors="ignore") if isinstance(line, bytes) else line
            # 匹配类似 "* 50 EXISTS" 的行
            match = re.search(r"\*\s+(\d+)\s+EXISTS", line_str)
            if match:
                total_emails = int(match.group(1))
                break

        result["total_emails"] = total_emails

        # 5. 统计未读邮件数
        search_response = await imap_client.search("UNSEEN")

        if search_response.result == "OK":
            email_ids_bytes = search_response.lines[0]
            email_ids_str = email_ids_bytes.decode("utf-8", errors="ignore")
            email_ids = email_ids_str.split() if email_ids_str.strip() else []
            result["unseen_emails"] = len(email_ids)
        else:
            result["unseen_emails"] = 0

        # 6. 探测成功
        result["success"] = True
        result["elapsed_time"] = time.time() - start_time

        if verbose:
            print("  ✓ 探测成功")

        return result

    except asyncio.TimeoutError:
        result["error"] = "连接超时"
        result["elapsed_time"] = time.time() - start_time
        return result

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)}"
        result["elapsed_time"] = time.time() - start_time
        return result

    finally:
        # 7. 清理连接
        if imap_client:
            try:
                await imap_client.logout()
            except Exception:
                pass


async def async_main(args: argparse.Namespace) -> int:
    """异步主函数。

    Args:
        args: 命令行参数

    Returns:
        退出码（0 成功，1 失败）
    """
    # 1. 加载账号配置
    try:
        manager = get_account_manager()
    except Exception as e:
        print(f"❌ 加载账号配置失败: {e}")
        return 1

    # 2. 确定要探测的账号
    if args.email:
        # 探测指定账号
        account = manager.get_account_by_email(args.email)
        if not account:
            print(f"❌ 未找到邮箱账号: {args.email}")
            return 1
        accounts = [account]
    else:
        # 探测所有启用的账号
        accounts = manager.accounts
        if not accounts:
            print("❌ 未找到任何启用的邮箱账号")
            print("提示：请检查 backend/email_accounts.yaml 文件")
            return 1

    # 3. 打印探测信息
    print(f"📧 准备探测 {len(accounts)} 个邮箱账号...")
    if not args.verbose:
        print()

    # 4. 并发探测所有账号
    tasks = [check_account(acc, args.verbose) for acc in accounts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 5. 统计和输出结果
    success_count = 0
    failed_count = 0

    print("\n" + "=" * 80)
    print("探测结果汇总")
    print("=" * 80 + "\n")

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # 捕获到异常（不应该发生，因为 check_account 已经处理了所有异常）
            account = accounts[i]
            print(f"❌ {account.register_account}")
            print(f"   服务器: {account.imap_server}:{account.imap_port}")
            print(f"   错误: {str(result)}\n")
            failed_count += 1
        elif result["success"]:
            # 探测成功
            print(f"✅ {result['email']}")
            print(f"   服务器: {result['imap_server']}:{result['imap_port']}")
            print(f"   总邮件: {result['total_emails']} 封")
            print(f"   未读邮件: {result['unseen_emails']} 封")
            print(f"   耗时: {result['elapsed_time']:.2f} 秒\n")
            success_count += 1
        else:
            # 探测失败
            print(f"❌ {result['email']}")
            print(f"   服务器: {result['imap_server']}:{result['imap_port']}")
            print(f"   错误: {result['error']}")
            print(f"   耗时: {result['elapsed_time']:.2f} 秒\n")
            failed_count += 1

    # 6. 打印统计信息
    print("=" * 80)
    print(f"探测完成: 成功 {success_count} 个, 失败 {failed_count} 个")
    print("=" * 80)

    # 7. 返回退出码
    return 0 if failed_count == 0 else 1


def main() -> None:
    """主函数入口。"""
    parser = argparse.ArgumentParser(
        description="探测邮箱账号 IMAP 连接有效性并统计邮件数量",
        epilog="""示例：
  # 探测所有账号
  uv run python scripts/check_email_accounts.py

  # 探测指定账号
  uv run python scripts/check_email_accounts.py --email qw330650@163.com

  # 详细输出模式
  uv run python scripts/check_email_accounts.py --verbose
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--email",
        type=str,
        help="指定要探测的邮箱地址（register_account），不指定则探测所有账号",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细的连接过程信息",
    )

    args = parser.parse_args()

    # 运行异步主函数
    exit_code = asyncio.run(async_main(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
