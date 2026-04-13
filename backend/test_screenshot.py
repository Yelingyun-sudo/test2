#!/usr/bin/env python3
"""
测试脚本：验证使用 xdotool + pyautogui 截取 Chrome 浏览器窗口的可行性
运行命令
(backend) wangzhengyu@lib403:~/E/webAnaPro/website_analytics/backend$ uv run python test_screenshot.py 2>&1
功能：
1. 使用 xdotool 查找 Chrome 浏览器窗口
2. 激活并最大化窗口
3. 使用 pyautogui 截取整个屏幕

输出：
- 详细的调试信息
- 截图保存到脚本同级目录

用法：
    uv run python test_screenshot.py
    或直接运行: python3 test_screenshot.py

依赖：
    pip install pyautogui
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_PATH = SCRIPT_DIR / f"test_screenshot_{datetime.now().strftime('%H%M%S')}.png"

# 工具路径配置
XDOTOOL_PATHS = [
    Path.home() / ".local/bin/xdotool",
    Path("/usr/bin/xdotool"),
    Path("/usr/local/bin/xdotool"),
    Path("xdotool"),  # 从 PATH 中查找
]

def log(message: str, level: str = "INFO") -> None:
    """打印带时间戳的日志信息。"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] {message}")

def find_xdotool(paths: list[Path]) -> str | None:
    """在指定路径中查找 xdotool，返回可执行路径或 None。"""
    log("查找 xdotool 工具...")
    for path in paths:
        log(f"  尝试路径: {path}")
        if path.name == "xdotool":
            # 从 PATH 中查找
            result = subprocess.run(
                ["which", "xdotool"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = result.stdout.strip()
                log(f"  ✓ 从 PATH 中找到: {found_path}")
                return found_path
        elif path.exists() and path.is_file():
            log(f"  ✓ 找到: {path}")
            return str(path)
    log("  ✗ 未找到 xdotool", "ERROR")
    return None


def check_pyautogui() -> bool:
    """检查 pyautogui 是否已安装。"""
    log("检查 pyautogui 模块...")
    try:
        import pyautogui
        version = getattr(pyautogui, "__version__", "unknown")
        log(f"  ✓ pyautogui 已安装 (版本: {version})")
        return True
    except ImportError:
        log("  ✗ pyautogui 未安装", "ERROR")
        log("  请运行: pip install pyautogui", "ERROR")
        return False

def run_command(cmd: list[str], timeout: int = 10) -> tuple[bool, str, str]:
    """运行命令并返回结果。"""
    cmd_str = " ".join(cmd)
    log(f"执行命令: {cmd_str}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stdout:
            log(f"  stdout: {result.stdout.strip()[:200]}")
        if result.stderr:
            log(f"  stderr: {result.stderr.strip()[:200]}")
        log(f"  returncode: {result.returncode}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log(f"  ✗ 命令超时 (>{timeout}s)", "ERROR")
        return False, "", "timeout"
    except Exception as e:
        log(f"  ✗ 执行异常: {e}", "ERROR")
        return False, "", str(e)

def find_chrome_window(xdotool: str) -> str | None:
    """使用 xdotool 查找 Chrome 窗口 ID，选择面积最大的窗口。"""
    log("=" * 60)
    log("步骤 1: 查找 Chrome 浏览器窗口")
    log("=" * 60)

    all_candidates = []

    # 尝试多种搜索模式
    search_patterns = [
        ("class", "google-chrome"),
        ("class", "Google-chrome"),
        ("class", "chrome"),
        ("class", "Chrome"),
        ("class", "chromium"),
        ("class", "Chromium"),
        ("name", "Chrome"),
        ("name", "chrome"),
    ]

    for search_type, pattern in search_patterns:
        log(f"尝试搜索 --{search_type} '{pattern}'")
        success, stdout, stderr = run_command(
            [xdotool, "search", f"--{search_type}", pattern],
            timeout=5,
        )
        if success and stdout.strip():
            window_ids = stdout.strip().split("\n")
            log(f"✓ 找到 {len(window_ids)} 个窗口: {window_ids}")
            all_candidates.extend([wid.strip() for wid in window_ids if wid.strip()])

    if not all_candidates:
        log("✗ 无法找到 Chrome 窗口", "ERROR")
        return None

    # 去重并获取每个窗口的面积
    unique_windows = list(set(all_candidates))
    log(f"\n分析 {len(unique_windows)} 个唯一窗口的面积...")

    largest_window = None
    largest_area = 0
    window_info_list = []

    for wid in unique_windows:
        # 获取窗口几何信息
        success, geo_stdout, _ = run_command(
            [xdotool, "getwindowgeometry", wid],
            timeout=3,
        )
        if not success:
            continue

        # 获取窗口标题
        success_title, title_stdout, _ = run_command(
            [xdotool, "getwindowname", wid],
            timeout=3,
        )
        title = title_stdout.strip() if success_title else "未知"

        # 解析窗口大小
        width, height = 0, 0
        for line in geo_stdout.split("\n"):
            if "Geometry:" in line:
                parts = line.split("Geometry:")[-1].strip().split("x")
                if len(parts) == 2:
                    try:
                        width, height = int(parts[0]), int(parts[1])
                    except ValueError:
                        continue

        area = width * height
        window_info_list.append((wid, width, height, area, title))
        log(f"  窗口 {wid}: {width}x{height} = {area} 像素, 标题: {title[:30]}")

        # 选择面积最大的窗口（至少 800x600 = 480000 像素）
        if area > largest_area and area > 480000:
            largest_area = area
            largest_window = wid

    if largest_window:
        log(f"\n✓ 选择最大窗口: {largest_window} (面积: {largest_area})")
        return largest_window

    # 如果没有找到足够大的窗口，返回第一个候选
    if unique_windows:
        log(f"\n⚠ 未找到足够大的窗口，返回第一个候选: {unique_windows[0]}")
        return unique_windows[0]

    log("✗ 无法找到 Chrome 窗口", "ERROR")
    return None

def get_window_info(xdotool: str, window_id: str) -> None:
    """获取并显示窗口详细信息。"""
    log("=" * 60)
    log("步骤 2: 获取窗口信息")
    log("=" * 60)

    # 获取窗口标题
    success, stdout, _ = run_command(
        [xdotool, "getwindowname", window_id],
        timeout=3,
    )
    if success:
        log(f"窗口标题: {stdout.strip()}")

    # 获取窗口几何信息
    success, stdout, _ = run_command(
        [xdotool, "getwindowgeometry", window_id],
        timeout=3,
    )
    if success:
        log(f"窗口几何信息:\n{stdout}")

    # 获取窗口状态（是否最小化等）
    success, stdout, _ = run_command(
        [xdotool, "getwindowstate", window_id],
        timeout=3,
    )
    if success and stdout.strip():
        log(f"窗口状态: {stdout.strip()}")
    else:
        log("窗口状态: 正常")

def activate_and_maximize_window(xdotool: str, window_id: str) -> bool:
    """激活并最大化 Chrome 窗口。"""
    log("=" * 60)
    log("步骤 3: 激活并最大化窗口")
    log("=" * 60)

    import time

    # 首先尝试将窗口移到最前面
    log("尝试将窗口移到最前面 (windowraise)...")
    run_command([xdotool, "windowraise", window_id], timeout=5)

    # 激活窗口
    log("尝试激活窗口 (windowactivate)...")
    success, _, stderr = run_command(
        [xdotool, "windowactivate", window_id],
        timeout=5,
    )
    if success:
        log("✓ 窗口已激活")
    else:
        log(f"⚠ 激活窗口可能失败: {stderr}", "WARNING")

    # 等待窗口完全激活
    log("等待 0.5 秒让窗口完全激活...")
    time.sleep(0.5)

    # 最大化窗口
    log("尝试最大化窗口...")
    # 方法1: 使用 windowmaximize
    success, _, stderr = run_command(
        [xdotool, "windowmaximize", window_id],
        timeout=5,
    )
    if success:
        log("✓ 窗口已最大化 (windowmaximize)")
    else:
        # 方法2: 使用 key 发送 F11 (全屏)
        log("尝试使用 F11 全屏...")
        run_command([xdotool, "key", "F11"], timeout=3)
        log("✓ 已发送 F11 全屏键")

    # 等待窗口最大化完成
    log("等待 1 秒让窗口最大化完成...")
    time.sleep(1)

    return True

def take_screenshot(output_path: Path) -> bool:
    """使用 pyautogui 截取屏幕。

    由于窗口已最大化，截图将主要包含 Chrome 浏览器内容。
    """
    log("=" * 60)
    log("步骤 4: 使用 pyautogui 截取屏幕")
    log("=" * 60)

    import time

    try:
        import pyautogui
    except ImportError:
        log("✗ pyautogui 未安装，无法截图", "ERROR")
        return False

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"确保目录存在: {output_path.parent}")

    # 使用绝对路径
    abs_path = str(output_path.absolute())
    log(f"保存路径: {abs_path}")

    # 检查目录是否可写
    if not os.access(output_path.parent, os.W_OK):
        log(f"✗ 目录不可写: {output_path.parent}", "ERROR")
        return False

    # 等待一下确保窗口已完全最大化
    log("等待 0.5 秒后截图...")
    time.sleep(0.5)

    try:
        # 使用 pyautogui 截图
        log("调用 pyautogui.screenshot()...")
        screenshot = pyautogui.screenshot()

        # 保存截图
        screenshot.save(abs_path)
        log(f"✓ 截图已保存到: {abs_path}")

        # 验证文件
        if output_path.exists():
            file_size = output_path.stat().st_size
            width, height = screenshot.size
            log(f"✓ 截图成功!")
            log(f"  分辨率: {width}x{height}")
            log(f"  文件大小: {file_size} bytes ({file_size / 1024:.2f} KB)")
            return True
        else:
            log("✗ 截图文件未创建", "ERROR")
            return False

    except Exception as e:
        log(f"✗ 截图失败: {e}", "ERROR")
        return False

def main() -> int:
    """主函数。"""
    log("=" * 60)
    log("Chrome 浏览器截图测试工具 (使用 xdotool + pyautogui)")
    log("=" * 60)
    log(f"脚本目录: {SCRIPT_DIR}")
    log(f"输出路径: {OUTPUT_PATH}")
    log("")

    # 检查依赖
    xdotool = find_xdotool(XDOTOOL_PATHS)
    if not xdotool:
        log("错误: 未找到 xdotool 工具", "ERROR")
        log("请安装: sudo apt-get install xdotool", "ERROR")
        return 1

    if not check_pyautogui():
        log("请安装 pyautogui: pip install pyautogui", "ERROR")
        return 1

    log("")

    # 查找 Chrome 窗口
    window_id = find_chrome_window(xdotool)
    if not window_id:
        log("无法找到 Chrome 窗口，请确保:", "ERROR")
        log("  1. Chrome 浏览器已启动", "ERROR")
        log("  2. Chrome 不是最小化状态", "ERROR")
        return 1

    log("")

    # 获取窗口信息
    get_window_info(xdotool, window_id)
    log("")

    # 激活并最大化窗口
    activate_and_maximize_window(xdotool, window_id)
    log("")

    # 截图
    if not take_screenshot(OUTPUT_PATH):
        log("截图失败", "ERROR")
        return 1

    log("")
    log("=" * 60)
    log("测试完成!")
    log("=" * 60)
    log(f"截图已保存: {OUTPUT_PATH}")
    log(f"文件大小: {OUTPUT_PATH.stat().st_size / 1024:.2f} KB")
    return 0

if __name__ == "__main__":
    sys.exit(main())
