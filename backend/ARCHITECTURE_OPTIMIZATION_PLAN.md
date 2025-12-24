# 架构优化方案：程序化单入口巡检工具

## 核心思路

**完全移除 inspect_entry_agent**，创建一个程序化工具 `build_programmatic_inspect_entry_tool`，直接在工具内部调用 MCP server 的浏览器操作。

## 关键发现

`AutoSwitchingPlaywrightServer` 有 `async def call_tool(tool_name, arguments)` 方法，可以直接调用浏览器工具！

## 技术挑战与解决方案

### 挑战：异步/同步不匹配
- `@function_tool` 装饰的函数是**同步**的
- `playwright_server.call_tool()` 是**异步**的

### 解决方案：使用事件循环

```python
import asyncio
from typing import Any

def build_programmatic_inspect_entry_tool(
    task_dir: Path,
    playwright_server: AutoSwitchingPlaywrightServer,
) -> Tool:
    """创建完全程序化的单入口巡检工具。

    将 8 轮 LLM 调用减少到 1 轮！
    """
    inspect_dir = task_dir / "inspect"
    inspect_dir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="programmatic_inspect_entry",
        description_override="程序化巡检单个菜单入口，自动完成点击、截图、文本采集。",
    )
    def programmatic_inspect_entry(
        entry_id: str,
        entry_index: int,
        entry_label: str,
    ) -> str:
        """程序化巡检单个入口。

        Args:
            entry_id: 入口唯一标识
            entry_index: 入口序号
            entry_label: 菜单标签

        Returns:
            JSON 字符串，包含巡检结果
        """
        # 获取或创建事件循环
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 定义异步逻辑
        async def _do_inspect():
            try:
                # 1. 获取快照
                snapshot_result = await playwright_server.call_tool(
                    "browser_snapshot",
                    {"filename": "tmp_snapshot"}
                )

                # 2. 解析快照，匹配 entry_label
                snapshot_text = snapshot_result.content[0].text
                ref = _find_ref_by_label(snapshot_text, entry_label)
                if not ref:
                    return {
                        "entry_id": entry_id,
                        "status": "failed",
                        "screenshot": None,
                        "text_snapshot": None,
                        "error": f"菜单 '{entry_label}' 在快照中不存在。",
                    }

                # 3. 点击菜单
                await playwright_server.call_tool(
                    "browser_click",
                    {"ref": ref}
                )

                # 4. 等待加载
                await playwright_server.call_tool(
                    "browser_wait_for",
                    {"time": 2}
                )

                # 5. 截图
                safe_label = (
                    entry_label.strip()
                    .replace(" ", "_")
                    .translate(str.maketrans("", "", r'/\:*?"<>|'))
                )
                prefix = f"{entry_index:02d}_{safe_label}"
                screenshot_path = f"inspect/{prefix}.png"

                await playwright_server.call_tool(
                    "browser_take_screenshot",
                    {"filename": screenshot_path, "fullPage": True}
                )

                # 6. 获取文本
                text_result = await playwright_server.call_tool(
                    "browser_evaluate",
                    {"function": "() => document.body.innerText"}
                )
                text_content = text_result.content[0].text

                # 清理 Playwright 调试输出
                clean_text = text_content
                if clean_text.startswith("### Result\n\"") and clean_text.endswith('"'):
                    clean_text = clean_text[14:-1]
                elif clean_text.startswith("### Result\n"):
                    clean_text = clean_text[12:]

                # 7. 保存文本
                text_path = inspect_dir / f"{prefix}.txt"
                text_path.write_text(clean_text, encoding="utf-8")

                # 8. 保存 JSON
                result_data = {
                    "entry_id": entry_id,
                    "status": "success",
                    "screenshot": screenshot_path,
                    "text_snapshot": f"inspect/{prefix}.txt",
                    "error": None,
                }
                json_path = inspect_dir / f"{prefix}.json"
                json_path.write_text(
                    json.dumps(result_data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

                return result_data

            except Exception as exc:
                return {
                    "entry_id": entry_id,
                    "status": "failed",
                    "screenshot": None,
                    "text_snapshot": None,
                    "error": f"巡检失败：{exc}",
                }

        # 在当前事件循环中运行异步逻辑
        if loop.is_running():
            # 如果循环已运行，使用 create_task (Agent 运行时场景)
            import nest_asyncio
            nest_asyncio.apply()  # 允许嵌套事件循环
            result = loop.run_until_complete(_do_inspect())
        else:
            # 如果循环未运行，直接 run_until_complete
            result = loop.run_until_complete(_do_inspect())

        return json.dumps(result, ensure_ascii=False)

    return programmatic_inspect_entry


def _find_ref_by_label(snapshot_text: str, label: str) -> str | None:
    """从快照文本中查找匹配标签的 ref。

    简化版实现，使用正则表达式匹配。
    """
    import re
    # 匹配形式：<id:123> 套餐商店
    pattern = rf'<id:(\d+)>\s*{re.escape(label)}'
    match = re.search(pattern, snapshot_text)
    return match.group(1) if match else None
```

## 修改点

### 1. 移除 inspect_entry_agent

**文件**：`backend/core/website_analytics/orchestrator.py`

删除：
```python
inspect_entry_agent = build_inspect_entry_agent(...)
inspect_entry_tool = inspect_entry_agent.as_tool(...)
```

添加：
```python
programmatic_inspect_entry_tool = build_programmatic_inspect_entry_tool(
    working_dir,
    playwright_server,
)
```

### 2. 更新 inspect_agent 的工具列表

```python
inspect_agent = build_inspect_agent(
    playwright_server,
    load_instruction("inspect_agent.md"),
    extra_tools=[
        programmatic_inspect_entry_tool,  # 新工具
        compile_inspect_report_tool,
    ],
)
```

### 3. 更新 inspect_agent.md

调用新工具时，只需要 3 个参数：
```json
{
  "entry_id": "entry_01",
  "entry_index": 1,
  "entry_label": "套餐商店"
}
```

## 预期效果

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| **inspectEntry 轮数** | 24 轮 (3×8) | **3 轮** (3×1) | **87.5% ↓** |
| **总耗时** | 129.26s | **~40s** | **69% ↓** |
| **推理 tokens** | 3008 | **~500** | **83% ↓** |

## 潜在问题与解决

### 问题 1：nest_asyncio 依赖

**解决**：添加到 `pyproject.toml`：
```toml
[tool.poetry.dependencies]
nest-asyncio = "^1.6.0"
```

### 问题 2：快照解析复杂

**解决**：实现更健壮的 `_find_ref_by_label` 函数，参考原有 LLM 的匹配逻辑。

### 问题 3：错误处理

**解决**：在 `_do_inspect` 中添加详细的 try-except，记录每一步的失败原因。

## 实施步骤

1. 安装 `nest-asyncio`
2. 在 `tools.py` 中实现 `build_programmatic_inspect_entry_tool`
3. 修改 `orchestrator.py`，替换工具
4. 更新 `inspect_agent.md`，调整工具调用示例
5. 测试验证

## 风险评估

- **中等风险**：异步/同步转换需要测试
- **高回报**：轮数减少 87.5%
- **可回滚**：保留旧代码，随时切换
