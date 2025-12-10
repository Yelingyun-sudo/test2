# Backend（Python + FastAPI）

## 目录结构
- `core/website_analytics/`：核心逻辑/CLI
- `api/`：FastAPI 应用层
- `instructions/`：智能体提示词
- `resources/`：任务示例等
- `logs/`：运行输出

## 环境与依赖
```bash
cd backend
uv venv --python 3.12
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .         # 或 pip install -e .
```

## 配置
- `backend/.env`（示例见 `.env.example`）：`OPENAI_API_KEY`、`AGENT_MODEL`、`PLAYWRIGHT_PROXY_SERVER`、`INSPECT_MAX_MENU_ENTRIES`、`PROJECT_NAME`、`API_PREFIX` 等。

## 运行
- CLI：`python -m website_analytics.main --help` 或 `python -m website_analytics.main --instruction "..."`
- FastAPI：`uvicorn app.main:app --reload --app-dir api`
- 健康检查：`GET http://127.0.0.1:8000/api/health`

## API 模块（FastAPI）
- 入口与配置：`api/app/main.py` 挂载路由/CORS，配置统一复用 `website_analytics.settings`（pydantic-settings，默认读取 `backend/.env`）。
- 路由与模型：`api/app/routers/`（health、auth 示例）与 `api/app/schemas/`。
- 开发启动：`uvicorn app.main:app --reload --app-dir api`，访问 `http://127.0.0.1:8000/api/health`。
- 接入建议：将 mock 登录替换为真实鉴权；按需在 settings 扩展数据库、缓存等配置，调用 `website_analytics` 核心能力。

## 说明
- `settings.py` 会自动加载当前目录或 `backend/.env`；指令文件从 `backend/instructions/` 读取。
- 依赖 `openai-agents`（0.6.x）和 `openai` 2.x；本地开发通过 `pip install -e .`，不打包分发。
