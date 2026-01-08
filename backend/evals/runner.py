from __future__ import annotations

import argparse
import asyncio
import json
import random
import string
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import set_tracing_disabled
from website_analytics.cli import run_single_instruction
from website_analytics.output_types import ErrorType
from website_analytics.utils import LOGS_DIR, to_project_relative

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CASE_DIR = BASE_DIR


@dataclass
class Case:
    id: str
    url: str
    account: str
    password: str
    expected: dict[str, Any]
    enabled: bool = True
    source_file: Path | None = None

    @property
    def instruction(self) -> str:
        return f"登录 {self.url}（账号和密码分别为 {self.account} 和 {self.password}）并提取订阅地址"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate website analytics cases.")
    parser.add_argument(
        "--case-file",
        action="append",
        type=Path,
        help="指定一个或多个用例文件（默认扫描 backend/tests/eval/*.json）",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="最大并发任务数（默认 1，可用 MAX_CONCURRENT 覆盖）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式运行浏览器（不显示界面）",
    )
    return parser.parse_args()


def _load_cases(files: list[Path]) -> list[Case]:
    cases: list[Case] = []
    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(f"用例文件不存在: {file_path}")
        content = file_path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except Exception as exc:
            raise ValueError(f"用例文件解析失败: {file_path}，错误：{exc}") from exc
        if not isinstance(data, list):
            raise ValueError(f"用例文件必须是数组: {file_path}")
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"用例项必须是对象: {file_path}")
            enabled = bool(item.get("enabled", True))
            if not enabled:
                continue
            expected = item.get("expected") or {}
            if "success" not in expected:
                raise ValueError(f"expected.success 缺失: {file_path}")
            success = bool(expected["success"])
            if success:
                if "subscription_url_prefix" not in expected:
                    raise ValueError(
                        f"成功用例缺少 subscription_url_prefix: {file_path}"
                    )
            else:
                if "error_type" not in expected:
                    raise ValueError(f"失败用例缺少 error_type: {file_path}")
                # 校验 error_type 是否在枚举中
                try:
                    ErrorType(expected["error_type"])
                except Exception as exc:
                    raise ValueError(
                        f"未知 error_type '{expected['error_type']}' in {file_path}"
                    ) from exc

            case = Case(
                id=str(item.get("id", "")),
                url=str(item.get("url", "")),
                account=str(item.get("account", "")),
                password=str(item.get("password", "")),
                expected=expected,
                enabled=True,
                source_file=file_path,
            )
            cases.append(case)
    return cases


def _find_case_files(args_files: list[Path] | None) -> list[Path]:
    if not args_files:
        return sorted(DEFAULT_CASE_DIR.glob("*.json"))

    resolved: list[Path] = []
    for p in args_files:
        if p.is_absolute():
            resolved.append(p)
            continue
        # 优先按工作目录解析
        candidate = (Path.cwd() / p).resolve()
        if candidate.exists():
            resolved.append(candidate)
            continue
        # 兜底：相对默认用例目录解析
        alt = (DEFAULT_CASE_DIR / p).resolve()
        resolved.append(alt)
    return resolved


def _extract_coordinator(result: Any) -> dict[str, Any]:
    if result and getattr(result, "coordinator_output", None):
        return result.coordinator_output  # type: ignore[no-any-return]
    # fallback: try task_summary.json
    if result and getattr(result, "task_dir", None):
        summary_path = Path(result.task_dir) / "task_summary.json"
        if summary_path.exists():
            try:
                with summary_path.open("r", encoding="utf-8") as f:
                    summary = json.load(f)
                return summary.get("coordinator_output") or {}
            except Exception:
                return {}
    return {}


def _build_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    run_dir = LOGS_DIR / f"eval_{timestamp}_{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _evaluate_case(case: Case, coordinator: dict[str, Any]) -> tuple[bool, str]:
    status = str(coordinator.get("status", "")).lower()
    if status not in {"success", "failed"}:
        return False, "coordinator status 缺失或非法"

    expected = case.expected
    success_expected = bool(expected["success"])

    if success_expected and status != "success":
        return False, "期望 success，但实际 failed"
    if not success_expected and status != "failed":
        return False, "期望 failed，但实际 success"

    operations = coordinator.get("operations_results") or {}
    extract_result = operations.get("extract") or {}

    if success_expected:
        url = extract_result.get("subscription_url") or ""
        prefix = expected.get("subscription_url_prefix") or ""
        if not url:
            return False, "缺少 subscription_url"
        if not str(url).startswith(str(prefix)):
            return False, "subscription_url 前缀不匹配"
        return True, "success"

    # failed path
    error_type = coordinator.get("error_type")
    expected_error = expected.get("error_type")
    if expected_error and error_type != expected_error:
        return False, f"error_type 不匹配，期望 {expected_error} 实际 {error_type}"

    return True, "failed as expected"


async def _run_case(case: Case, headless: bool) -> dict[str, Any]:
    exec_result = await asyncio.to_thread(
        run_single_instruction,
        case.instruction,
        headless=headless,
    )
    coordinator = _extract_coordinator(exec_result)
    passed, reason = _evaluate_case(case, coordinator)
    task_dir = (
        to_project_relative(exec_result.task_dir)
        if exec_result and exec_result.task_dir
        else None
    )
    return {
        "case_id": case.id,
        "source_file": str(case.source_file) if case.source_file else "",
        "passed": passed,
        "reason": reason,
        "task_dir": str(task_dir) if task_dir else "",
        "coordinator_output": coordinator,
    }


async def main_async(args: argparse.Namespace) -> None:
    case_files = _find_case_files(args.case_file)
    cases = _load_cases(case_files)
    if not cases:
        print("没有可执行的用例")
        return

    run_dir = _build_run_dir()

    max_concurrent = args.max_concurrent
    if max_concurrent is None:
        # 默认 1，可被环境变量覆盖（Makefile 中传入）
        max_concurrent = 1

    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[dict[str, Any]] = []

    async def worker(case: Case):
        async with semaphore:
            result = await _run_case(case, headless=args.headless)
            results.append(result)

    tasks = [asyncio.create_task(worker(case)) for case in cases]
    await asyncio.gather(*tasks)

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print(f"用例执行完成：总数 {len(results)}，通过 {passed}，失败 {failed}")

    result_file = run_dir / "eval_results.json"
    meta_file = run_dir / "meta.json"
    result_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = {
        "case_files": [str(p) for p in case_files],
        "max_concurrent": max_concurrent,
        "headless": bool(args.headless),
        "run_dir": str(run_dir),
        "timestamp": datetime.now().isoformat(),
    }
    meta_file.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"结果已保存到 {result_file}")


def main() -> None:
    # 评估不需要 tracing
    set_tracing_disabled(True)
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
