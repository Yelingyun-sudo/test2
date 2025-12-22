#!/usr/bin/env python3
"""批量拉取站点详情脚本。

从分页接口获取所有 records，然后对每个 record 调用 getInfoById 获取详细信息。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  python %(prog)s --url http://43.143.137.121:8081 --cookie JSESSIONID=xxxxx
  python %(prog)s --url http://43.143.137.121:8081 --cookie JSESSIONID=xxxxx --output output.json
  python %(prog)s --url http://43.143.137.121:8081 --cookie JSESSIONID=xxxxx --limit 10
""",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="API 基础 URL（如 http://43.143.137.121:8081）",
    )
    parser.add_argument(
        "--cookie",
        required=True,
        help="Cookie 字符串（如 JSESSIONID=xxxxx）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("resources/site_details.json"),
        help="输出 JSON 文件路径（默认：resources/site_details.json）",
    )
    parser.add_argument(
        "--status",
        type=int,
        default=3,
        help="筛选任务状态（默认：3 表示已完成）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="每页记录数（默认：10）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="最大页数限制（用于测试，不设置则拉取所有页）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="请求间隔（秒，默认：0.5）",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="禁用 SSL 证书验证（等价于 curl --insecure）",
    )
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    return args


def create_session(cookie: str, verify: bool = True) -> requests.Session:
    """创建 requests Session，配置重试策略和 Cookie。"""
    session = requests.Session()
    
    # 配置重试策略
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # 设置请求头
    session.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
        "Connection": "keep-alive",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    })
    
    # 设置 Cookie
    session.headers.update({"Cookie": cookie})
    
    # SSL 验证
    session.verify = verify
    
    return session


def fetch_page_list(
    session: requests.Session,
    base_url: str,
    page: int,
    limit: int,
    status: int,
) -> dict[str, Any] | None:
    """获取分页列表数据。"""
    url = f"{base_url}/site/pageSiteList"
    params = {
        "page": page,
        "limit": limit,
        "status": status,
    }
    
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"❌ 获取第 {page} 页失败: {e}")
        return None


def fetch_site_detail(
    session: requests.Session,
    base_url: str,
    site_id: int,
) -> dict[str, Any] | None:
    """根据 ID 获取站点详细信息。"""
    url = f"{base_url}/site/getInfoById"
    
    # 设置表单请求头
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": base_url,
        "Referer": f"{base_url}/site/viewInfo?id={site_id}",
    }
    
    data = {"id": site_id}
    
    try:
        response = session.post(url, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"  ❌ 获取站点 {site_id} 详情失败: {e}")
        return None


def main() -> None:
    """主函数。"""
    args = parse_args()
    
    # 创建 Session
    verify_ssl = not args.no_verify
    session = create_session(args.cookie, verify=verify_ssl)
    
    if args.no_verify:
        # 禁用 SSL 警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("🚀 开始拉取站点数据...")
    print(f"   基础 URL: {args.url}")
    print(f"   状态筛选: {args.status}")
    print(f"   每页记录: {args.limit}")
    print(f"   请求间隔: {args.delay} 秒")
    print()
    
    # 第一步：分页获取所有 records
    all_records: list[dict[str, Any]] = []
    page = 1
    total_pages = None
    
    while True:
        if args.max_pages and page > args.max_pages:
            print(f"⚠️  已达到最大页数限制 ({args.max_pages})，停止拉取")
            break
        
        print(f"📄 正在获取第 {page} 页...")
        result = fetch_page_list(session, args.url, page, args.limit, args.status)
        
        if not result or result.get("code") != 200:
            print(f"❌ 第 {page} 页返回错误或无数据")
            break
        
        data = result.get("data", {})
        records = data.get("records", [])
        total_pages = data.get("pages", 0)
        total_count = data.get("total", 0)
        
        if not records:
            print(f"✅ 第 {page} 页无数据，分页拉取结束")
            break
        
        all_records.extend(records)
        print(f"   ✓ 获取到 {len(records)} 条记录（累计 {len(all_records)}/{total_count}）")
        
        if page >= total_pages:
            print(f"✅ 已拉取所有 {total_pages} 页")
            break
        
        page += 1
        time.sleep(args.delay)
    
    print()
    print(f"📊 共获取 {len(all_records)} 条 record")
    print()
    
    # 第二步：对每个 record 获取详细信息
    detailed_results: list[dict[str, Any]] = []
    failed_ids: list[int] = []
    
    print("🔍 开始获取每个站点的详细信息...")
    print()
    
    for idx, record in enumerate(all_records, 1):
        site_id = record.get("id")
        if not site_id:
            print(f"  ⚠️  [{idx}/{len(all_records)}] record 缺少 id，跳过")
            continue
        
        print(f"  [{idx}/{len(all_records)}] 正在获取站点 {site_id} 的详细信息...")
        
        detail_result = fetch_site_detail(session, args.url, site_id)
        
        if detail_result and detail_result.get("code") == 200:
            detail_data = detail_result.get("data", {})
            detailed_results.append(detail_data)
            print(f"    ✓ 成功获取站点 {site_id} 详情")
        else:
            failed_ids.append(site_id)
            print(f"    ❌ 获取站点 {site_id} 详情失败")
        
        # 控制请求频率
        if idx < len(all_records):
            time.sleep(args.delay)
    
    print()
    print(f"✅ 详情获取完成：成功 {len(detailed_results)} 条，失败 {len(failed_ids)} 条")
    
    if failed_ids:
        print(f"⚠️  失败的站点 ID: {failed_ids}")
    
    # 第三步：保存结果
    output_data = {
        "total": len(detailed_results),
        "failed_count": len(failed_ids),
        "failed_ids": failed_ids,
        "records": detailed_results,
    }
    
    # 确保输出目录存在
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"💾 结果已保存到: {args.output}")
    print(f"   总记录数: {len(detailed_results)}")
    print(f"   文件大小: {args.output.stat().st_size / 1024:.2f} KB")
    print()
    print("🎉 任务完成！")


if __name__ == "__main__":
    main()

