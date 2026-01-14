#!/usr/bin/env python3
"""
Cloudflare Bypass Docker 使用示例

展示如何调用 Docker 容器获取 cookies，然后用 requests 发送后续请求。
"""

import subprocess
import json
import sys


def get_cloudflare_cookies(url: str, wait: int = 5, max_wait: int = 50) -> dict:
    """
    调用 Docker 容器获取 Cloudflare cookies
    
    Args:
        url: 目标 URL
        wait: 初始等待时间（秒）
        max_wait: 最大等待时间（秒）
        
    Returns:
        dict: 包含 success, cookies, user_agent, final_url 等字段
    """
    cmd = [
        'docker', 'run', '--rm',
        '--shm-size=2g',
        'cloudflare-bypass',
        url,
        '--output-json',
        '--wait', str(wait),
        '--max-wait', str(max_wait),
        '--retry', '1',
    ]
    
    print(f"[*] 正在调用 Docker 容器绕过 Cloudflare...")
    print(f"[*] 目标 URL: {url}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_wait + 60  # 额外 60 秒用于容器启动
        )
        
        # 解析 JSON 输出（从 stdout 的最后一行获取）
        stdout_lines = result.stdout.strip().split('\n')
        
        # 找到 JSON 行（以 { 开头）
        json_line = None
        for line in reversed(stdout_lines):
            line = line.strip()
            if line.startswith('{'):
                json_line = line
                break
        
        if json_line:
            data = json.loads(json_line)
            return data
        else:
            return {
                'success': False,
                'error': 'No JSON output found',
                'stdout': result.stdout,
                'stderr': result.stderr,
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Docker container timed out',
        }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'error': f'Failed to parse JSON: {e}',
            'stdout': result.stdout,
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


def example_with_requests():
    """使用 requests 库的示例"""
    try:
        import requests
    except ImportError:
        print("[!] 请先安装 requests: pip install requests")
        return
    
    url = "https://example.com"  # 替换为实际 URL
    
    # 1. 获取 cookies
    result = get_cloudflare_cookies(url)
    
    if not result.get('success'):
        print(f"[!] 绕过失败: {result.get('error')}")
        return
    
    print(f"[✓] 绕过成功！")
    print(f"[*] cf_clearance: {result['cookies'].get('cf_clearance', 'N/A')[:50]}...")
    
    # 2. 创建 session 并设置 cookies
    session = requests.Session()
    
    # 设置所有 cookies
    for name, value in result['cookies'].items():
        session.cookies.set(name, value)
    
    # 设置 User-Agent（必须与获取 cookies 时的 UA 一致）
    session.headers['User-Agent'] = result['user_agent']
    
    # 3. 发送请求
    print(f"\n[*] 使用获取的 cookies 发送请求...")
    response = session.get(result['final_url'])
    
    print(f"[*] 状态码: {response.status_code}")
    print(f"[*] 响应长度: {len(response.text)} 字符")
    print(f"[*] 响应内容预览: {response.text[:200]}...")


def example_with_curl():
    """生成 curl 命令的示例"""
    url = "https://example.com"  # 替换为实际 URL
    
    # 1. 获取 cookies
    result = get_cloudflare_cookies(url)
    
    if not result.get('success'):
        print(f"[!] 绕过失败: {result.get('error')}")
        return
    
    print(f"[✓] 绕过成功！")
    
    # 2. 生成 curl 命令
    cookies_str = '; '.join([f"{k}={v}" for k, v in result['cookies'].items()])
    user_agent = result['user_agent']
    final_url = result['final_url']
    
    curl_cmd = f'''curl -X GET "{final_url}" \\
    -H "Cookie: {cookies_str}" \\
    -H "User-Agent: {user_agent}"'''
    
    print(f"\n[*] 生成的 curl 命令:")
    print("-" * 60)
    print(curl_cmd)
    print("-" * 60)


def main():
    """主函数：演示用法"""
    if len(sys.argv) < 2:
        print("用法: python example_usage.py <URL>")
        print("")
        print("示例:")
        print("  python example_usage.py https://example.com")
        return
    
    url = sys.argv[1]
    
    # 获取 cookies
    print("=" * 60)
    print("Cloudflare Bypass Docker 使用示例")
    print("=" * 60)
    
    result = get_cloudflare_cookies(url)
    
    print("\n" + "=" * 60)
    print("结果")
    print("=" * 60)
    
    if result.get('success'):
        print(f"状态: ✓ 成功")
        print(f"最终 URL: {result.get('final_url')}")
        print(f"User-Agent: {result.get('user_agent', '')[:60]}...")
        print(f"\nCookies:")
        for name, value in result.get('cookies', {}).items():
            value_preview = value[:50] + '...' if len(value) > 50 else value
            print(f"  {name}: {value_preview}")
        
        # 生成后续使用命令
        print("\n" + "-" * 60)
        print("后续使用方式:")
        print("-" * 60)
        
        cf_clearance = result['cookies'].get('cf_clearance', 'YOUR_CF_CLEARANCE')
        ua = result.get('user_agent', 'YOUR_USER_AGENT')
        
        print(f"\n# curl 命令:")
        print(f'curl -H "Cookie: cf_clearance={cf_clearance[:30]}..." \\')
        print(f'     -H "User-Agent: {ua[:50]}..." \\')
        print(f'     "{url}"')
        
        print(f"\n# Python requests:")
        print(f"import requests")
        print(f"session = requests.Session()")
        print(f"session.cookies.set('cf_clearance', '{cf_clearance[:30]}...')")
        print(f"session.headers['User-Agent'] = '{ua[:50]}...'")
        print(f"response = session.get('{url}')")
        
    else:
        print(f"状态: ✗ 失败")
        print(f"错误: {result.get('error')}")
        if result.get('stderr'):
            print(f"\nStderr:\n{result.get('stderr')}")


if __name__ == "__main__":
    main()
