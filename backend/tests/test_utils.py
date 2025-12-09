from datetime import datetime
from types import SimpleNamespace

import website_analytics.utils as utils


def test_load_instruction_supports_replacements(tmp_path, monkeypatch):
    instructions_dir = tmp_path / "instructions"
    instructions_dir.mkdir()
    instruction_file = instructions_dir / "sample.txt"
    instruction_file.write_text(" Hello {name}! \n", encoding="utf-8")

    monkeypatch.setattr(utils, "INSTRUCTIONS_DIR", instructions_dir)

    result = utils.load_instruction("sample.txt", {"{name}": "Tester"})

    assert result == "Hello Tester!"


def test_build_playwright_args_formats_and_handles_headless(tmp_path, monkeypatch):
    template = ("--output-dir={output_dir}", "--timeout=1000")
    monkeypatch.setattr(utils, "PLAYWRIGHT_ARGS_TEMPLATE", template)
    output_dir = tmp_path / "out"

    args = utils.build_playwright_args(output_dir, headless=False)
    args_headless = utils.build_playwright_args(output_dir, headless=True)

    assert args == [f"--output-dir={output_dir}", "--timeout=1000"]
    assert args_headless == [f"--output-dir={output_dir}", "--timeout=1000", "--headless"]


def test_generate_task_directory_creates_expected_path(tmp_path, monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):  # pragma: no cover - simple shim for determinism
            return cls(2024, 12, 31, 23, 59, 59)

    monkeypatch.setattr(utils, "datetime", FixedDatetime)
    monkeypatch.setattr(utils, "random", SimpleNamespace(choices=lambda *_args, **_kwargs: list("abcd")))

    root = tmp_path / "logs_root"
    task_dir = utils.generate_task_directory(root)

    assert task_dir.name == "task_20241231_235959_abcd"
    assert task_dir.exists() and task_dir.is_dir()
    assert task_dir.parent == root
