# 评估用例说明

- 用例文件：`backend/tests/eval/*.json`，顶层数组，字段：
  - `id`、`url`、`account`、`password`
  - `expected.success`（必填）
    - success=true 时必须有 `subscription_url_prefix`
    - success=false 时必须有 `error_type`（使用 Coordinator 的错误枚举）
  - `enabled`（默认 true）

# 运行方式

```bash
# 扫描全部用例文件
python -m backend.tests.eval.runner

# 指定用例文件
python -m backend.tests.eval.runner --case-file backend/tests/eval/wa_success_case.json
```

Make 约定：
```bash
make eval                     # 跑全部 JSON
make eval filename=wa_success_case.json  # 跑指定文件
# 可传 MAX_CONCURRENT=2 HEADLESS=1
```

# 结果位置

- 每次执行生成目录：`backend/logs/eval_<timestamp>_<suffix>/`
  - `eval_results.json`：用例断言结果
  - `meta.json`：运行元信息（用例文件、并发、headless 等）
