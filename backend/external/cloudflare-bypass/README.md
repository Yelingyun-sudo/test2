# Cloudflare Bypass Tool

基于 Docker 的 Cloudflare Turnstile 验证绕过工具。

## 功能介绍

该工具使用 `undetected-chromedriver` + `PyAutoGUI` 在 Docker 容器中模拟真实用户操作，自动完成 Cloudflare Turnstile 验证，获取 `cf_clearance` cookie 供后续 HTTP 请求使用。

### 核心特性

- **Docker 容器化**: 使用 Xvfb 虚拟显示，无需本地安装浏览器
- **多架构支持**: 支持 ARM64 和 AMD64 架构
- **JSON 输出**: 支持 `--output-json` 参数，方便脚本集成
- **人类化操作**: 贝塞尔曲线鼠标移动，模拟真实用户行为

## 快速开始

### 1. 构建 Docker 镜像

```bash
cd backend/external/cloudflare-bypass
docker build -t cloudflare-bypass .
```

### 2. 运行验证

```bash
# 方式 1：使用脚本运行（推荐）
./run_bypass.sh https://0109.cave01-s0in7j02.top/ --output-json

# 方式 2：直接使用 docker 命令
docker run --rm --shm-size=2g cloudflare-bypass https://0109.cave01-s0in7j02.top/ --output-json

# 方式 3：直接运行 Python 脚本（本地开发测试）
# 需要先安装依赖：
cd backend/external/cloudflare-bypass
source ../../.venv/bin/activate  # 激活项目虚拟环境
uv pip install -r requirements.txt

# 运行脚本（需要本地已安装 Chromium）
python bypass_cloudflare_docker.py https://0109.cave01-s0in7j02.top/ --browser chromium --max-wait 60
```

### 3. 获取结果

成功时输出 JSON 格式结果：

```json
{
  "success": true,
  "url": "https://0109.cave01-s0in7j02.top/",
  "final_url": "https://0109.cave01-s0in7j02.top/",
  "cookies": {
    "cf_clearance": "xxx...",
    "__cf_bm": "xxx..."
  },
  "cf_clearance": "xxx...",
  "user_agent": "Mozilla/5.0 ...",
  "title": "...",
  "duration": 12.5,
  "error": ""
}
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `url` | (必填) | 目标 URL |
| `--output-json` | false | 输出纯 JSON 格式（推荐脚本调用时使用） |
| `--wait` | 5 | 初始等待时间（秒） |
| `--max-wait` | 50 | 最大等待时间（秒） |
| `--retry` | 1 | 最大重试次数 |
| `--browser` | auto | 浏览器选择：auto / chrome / chromium |

## 验证 Cookies 有效性

获取 cookies 后，可以通过以下方式验证其有效性。

### 步骤 1：获取 JSON 输出

```bash
RESULT=$(docker run --rm --shm-size=2g cloudflare-bypass \
    https://0109.cave01-s0in7j02.top/ --output-json --max-wait 60 2>/dev/null)

echo "$RESULT" | jq .
```

### 步骤 2：提取并使用 cookies

#### 方式 A：用 curl 验证

```bash
# 提取 cookies 和 User-Agent
CF_COOKIE=$(echo "$RESULT" | jq -r '.cf_clearance')
USER_AGENT=$(echo "$RESULT" | jq -r '.user_agent')

# 用 curl 访问（不经过 Docker）
curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Cookie: cf_clearance=$CF_COOKIE" \
    -H "User-Agent: $USER_AGENT" \
    "https://0109.cave01-s0in7j02.top/"

# 对比测试，不带cookies，预期返回403
curl -s -o /dev/null -w "状态码: %{http_code}\n" \
    -H "User-Agent: $USER_AGENT" \
    "https://0109.cave01-s0in7j02.top/"
```

如果返回 `200`，说明 cookies 有效！

#### 方式 B：用 Python requests 验证

```python
import subprocess
import json
import requests

# 1. 调用 Docker 获取 cookies
result = subprocess.run([
    'docker', 'run', '--rm', '--shm-size=2g', 'cloudflare-bypass',
    'https://0109.cave01-s0in7j02.top/', '--output-json', '--max-wait', '60'
], capture_output=True, text=True)

# 从 stdout 解析 JSON（stderr 是日志）
data = json.loads(result.stdout.strip())

print(f"成功: {data['success']}")
print(f"cf_clearance: {data['cf_clearance'][:50]}...")

# 2. 使用 cookies 发送请求
session = requests.Session()
for name, value in data['cookies'].items():
    session.cookies.set(name, value)
session.headers['User-Agent'] = data['user_agent']

# 3. 访问目标网站
response = session.get('https://0109.cave01-s0in7j02.top/')
print(f"状态码: {response.status_code}")
print(f"内容预览: {response.text[:100]}...")
```

### 完整 Shell 脚本示例

```bash
#!/bin/bash
# get_cloudflare_cookies.sh

URL="${1:-https://0109.cave01-s0in7j02.top/}"

echo "获取 Cloudflare cookies..."

RESULT=$(docker run --rm --shm-size=2g cloudflare-bypass "$URL" --output-json --max-wait 60 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "获取失败"
    exit 1
fi

SUCCESS=$(echo "$RESULT" | jq -r '.success')
if [ "$SUCCESS" != "true" ]; then
    echo "验证失败"
    exit 1
fi

CF_COOKIE=$(echo "$RESULT" | jq -r '.cf_clearance')
USER_AGENT=$(echo "$RESULT" | jq -r '.user_agent')

echo "✓ 获取成功！"
echo ""
echo "# 使用以下命令访问:"
echo "curl -H \"Cookie: cf_clearance=$CF_COOKIE\" \\"
echo "     -H \"User-Agent: $USER_AGENT\" \\"
echo "     \"$URL\""
```

## 在 website_analytics 中集成

### Python 调用示例

```python
import subprocess
import json

def get_cloudflare_cookies(url: str, max_wait: int = 50) -> dict:
    """调用 Docker 容器获取 Cloudflare cookies"""
    cmd = [
        'docker', 'run', '--rm',
        '--shm-size=2g',
        'cloudflare-bypass',
        url,
        '--output-json',
        '--max-wait', str(max_wait),
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=max_wait + 60
    )
    
    # 从 stdout 解析 JSON
    for line in reversed(result.stdout.strip().split('\n')):
        if line.strip().startswith('{'):
            return json.loads(line)
    
    return {'success': False, 'error': 'No JSON output'}


# 使用示例
result = get_cloudflare_cookies('https://0109.cave01-s0in7j02.top/')

if result['success']:
    cookies = result['cookies']
    user_agent = result['user_agent']
    
    # 使用获取的 cookies 发送请求
    import requests
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value)
    session.headers['User-Agent'] = user_agent
    
    response = session.get('https://0109.cave01-s0in7j02.top/')
```

### 与 Playwright 配合使用

```python
from playwright.async_api import async_playwright

async def use_cf_cookies_with_playwright(url: str):
    # 1. 获取 cf_clearance cookies
    result = get_cloudflare_cookies(url)
    
    if not result['success']:
        raise Exception(f"获取 cookies 失败: {result.get('error')}")
    
    # 2. 在 Playwright 中设置 cookies
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent=result['user_agent']
        )
        
        # 设置 cookies
        cookies = [
            {'name': name, 'value': value, 'domain': '.0109.cave01-s0in7j02.top', 'path': '/'}
            for name, value in result['cookies'].items()
        ]
        await context.add_cookies(cookies)
        
        page = await context.new_page()
        await page.goto(url)
        # ... 继续操作
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `bypass_cloudflare_docker.py` | 主程序，Cloudflare 绕过逻辑 |
| `Dockerfile` | Docker 镜像构建文件 |
| `entrypoint.sh` | 容器入口脚本，启动 Xvfb 虚拟显示 |
| `run_bypass.sh` | 主机调用脚本，简化 docker run 命令 |
| `example_usage.py` | Python 调用示例代码 |
| `requirements.txt` | Python 依赖 |

## 注意事项

1. **首次构建耗时较长**: Docker 镜像包含 Chromium 浏览器，构建可能需要几分钟
2. **共享内存**: 必须使用 `--shm-size=2g` 参数，否则 Chrome 可能崩溃
3. **成功率**: 不保证 100% 成功，某些网站可能有额外的反爬措施
4. **Cookie 有效期**: `cf_clearance` cookie 通常有效期为 30 分钟至数小时
5. **User-Agent 一致性**: 使用 cookies 发送请求时，必须使用相同的 User-Agent

## 故障排查

### 镜像构建失败

```bash
# 清理缓存重新构建
docker build --no-cache -t cloudflare-bypass .
```

### 容器运行超时

```bash
# 增加等待时间
./run_bypass.sh https://0109.cave01-s0in7j02.top/ --max-wait 120
```

### 验证失败

某些网站可能需要多次重试：

```bash
./run_bypass.sh https://0109.cave01-s0in7j02.top/ --retry 3 --max-wait 60
```

## 测试命令行

```bash
cloudflare人机验证
uv run python -m website_analytics.main --instruction '访问 https://0109.cave01-s0in7j02.top/ 注册账号并完成巡检'
uv run python -m website_analytics.main --instruction '访问 http://ouucloud.top 注册账号并完成巡检'
uv run python -m website_analytics.main --instruction '访问 https://xn--9kqz23b19z.com 注册账号并完成巡检'

需要邮箱验证码
uv run python -m website_analytics.main --instruction '访问 https://u.wuhenlink.cc 注册账号并完成巡检'

不需要邮箱验证码 + 邮箱完整
uv run python -m website_analytics.main --instruction '访问 https://a04.ffvipaffb04.cc 注册账号并登录，最终完成取证'
uv run python -m website_analytics.main --instruction '访问 https://zsigzoiupqwasdfl.hl-jsq.bond 注册账号并登录，最终完成取证'
uv run python -m website_analytics.main --instruction '访问 https://a11.qytvipaffa01.cc 注册账号并登录，最终完成取证'

不需要邮箱验证码 + 邮箱前缀
uv run python -m website_analytics.main --instruction '访问 http://www.yueqianvpn.com 注册账号并登录，最终完成取证'
uv run python -m website_analytics.main --instruction '登录 https://a11.qytvipaffa01.cc 用户名和密码分别是 wangqian674@163.com 和 test1234，并完成取证'
uv run python -m website_analytics.main --instruction '访问 https://a04.ffvipaffb04.cc 注册账号并登录，最终完成取证'
```bash