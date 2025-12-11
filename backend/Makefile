# PyPI 镜像源配置（阿里云源）
export UV_INDEX_URL := https://mirrors.aliyun.com/pypi/simple

# 默认目标：显示帮助信息
.DEFAULT_GOAL := help

PY_SRC := core api

.PHONY: help
help:  ## 显示可用的 make 命令
	@echo "可用的 make 命令："
	@echo ""
	@grep -E '^[a-zA-Z_][a-zA-Z0-9_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: format
format:  ## 自动格式化代码并修复 lint 问题
	uv run --with ruff ruff format $(PY_SRC)
	uv run --with ruff ruff check --fix $(PY_SRC)

.PHONY: lint
lint:  ## 运行 ruff linter
	uv run --with ruff ruff check $(PY_SRC)

.PHONY: test
test:  ## 运行所有测试
	uv run --with pytest pytest

.PHONY: test-e2e
test-e2e:  ## 运行端到端示例任务
	uv run python -m website_analytics.main --instruction "登录 https://api.778833.xyz（账号和密码分别为 mayorwang@163.com 和 Sh33024545 ）并提取订阅地址"

.PHONY: eval
eval:  ## 执行评估用例，默认跑 tests/eval/*.json；filename=xx.json 指定文件；输出到 logs/eval_*；MAX_CONCURRENT/HEADLESS 可调
	uv run python tests/eval/runner.py $(if $(filename),--case-file tests/eval/$(filename),) $(if $(MAX_CONCURRENT),--max-concurrent $(MAX_CONCURRENT),) $(if $(HEADLESS),--headless,)

.PHONY: check
check: lint test  ## 运行代码检查与测试
