"""
main.py 文件是 Website Analytics 后端服务的 FastAPI 应用入口
它负责：
配置全局日志系统。
创建并配置 FastAPI 应用（CORS、路由、依赖注入）。
管理应用生命周期：启动时根据配置开启多个后台循环任务（任务执行器、导入器、清理器、报告器等），关闭时优雅停止这些任务。
"""

import asyncio
import contextlib
import logging
import logging.config
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from website_analytics.settings import get_settings

from .db import init_db
from .routers import auth, health, payment, subscription, evidence
from .security import get_current_user
from .task_cleaner import run_task_cleaner_loop
from .task_importer import run_task_importer_loop
from .task_reporter import run_task_reporter_loop
from .task_runner_evidence import run_evidence_runner_loop
from .task_runner_subscription import run_subscription_runner_loop
from .task_runner_payment import run_payment_runner_loop

# 确保日志目录存在
_logs_dir = Path(__file__).resolve().parents[2] / "logs"
_logs_dir.mkdir(parents=True, exist_ok=True)
_console_log_path = _logs_dir / "console.log"

# 统一日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(_console_log_path),
            "maxBytes": 50 * 1024 * 1024,  # 50MB
            "backupCount": 10,
            "encoding": "utf-8",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["default", "file"],
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "httpx": {"level": "WARNING"},
        "kafka": {"level": "WARNING"},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)


# FastAPI 启动时初始化 run_evidence_runner_loop
# 这是 FastAPI 的异步生命周期管理器。它的作用是在应用启动时开启后台协程，在应用关闭时取消并等待它们结束。
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # 启动逻辑
    # 从配置中读取各个开关
    if settings.task_runner_enabled_subscription:  # 启动订阅任务执行器循环
        app.state.subscription_runner = asyncio.create_task(
            run_subscription_runner_loop()
        )
    if settings.task_runner_enabled_evidence:  # 启动证据任务执行器循环
        app.state.evidence_runner = asyncio.create_task(
            run_evidence_runner_loop()
        )  # 对于每个启用的功能，使用 asyncio.create_task 将对应的 run_xxx_loop() 协程作为后台任务启动，并把任务对象保存在 app.state 中（便于后续取消）。
    if settings.task_runner_enabled_payment:  # 启动支付任务执行器循环
        app.state.payment_runner = asyncio.create_task(run_payment_runner_loop())
    if settings.task_cleaner_enabled:  # 启动任务清理器循环
        app.state.task_cleaner = asyncio.create_task(run_task_cleaner_loop())
    if settings.task_importer_enabled:  # 启动任务导入器循环
        app.state.task_importer = asyncio.create_task(run_task_importer_loop())
    if settings.task_reporter_enabled:  # 启动任务报告器循环
        app.state.task_reporter = asyncio.create_task(run_task_reporter_loop())

    yield

    # 关闭逻辑
    # 这样设计保证了后台任务与 FastAPI 应用的生命周期一致，不会留下孤儿协程。
    if settings.task_runner_enabled_subscription:
        task = getattr(
            app.state, "subscription_runner", None
        )  # 对每个可能启动过的任务，尝试从 app.state 获取任务对象。调用 task.cancel() 发送取消信号。用 contextlib.suppress(Exception, asyncio.CancelledError) 等待任务完成，忽略可能抛出的取消异常，确保应用可以干净关闭。
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
    if settings.task_runner_enabled_evidence:
        task = getattr(app.state, "evidence_runner", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
    if settings.task_runner_enabled_payment:
        task = getattr(app.state, "payment_runner", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
    if settings.task_cleaner_enabled:
        task = getattr(app.state, "task_cleaner", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
    if settings.task_importer_enabled:
        task = getattr(app.state, "task_importer", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
    if settings.task_reporter_enabled:
        task = getattr(app.state, "task_reporter", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task


# 3. 创建 FastAPI 应用（create_app）
def create_app() -> FastAPI:
    settings = get_settings()  # 获取配置对象。
    init_db()  # 调用 init_db() 初始化数据库连接和表结构。
    app = FastAPI(
        title=settings.project_name, lifespan=lifespan
    )  # 创建 FastAPI 实例，指定标题和生命周期管理函数 lifespan。

    # 后续可按环境收紧
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # 公开接口（无需鉴权）
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)

    # 受保护接口：统一依赖要求已登录
    protected_dep = [Depends(get_current_user)]
    app.include_router(
        subscription.router,
        prefix=settings.api_prefix,
        dependencies=protected_dep,
    )
    app.include_router(
        evidence.router,
        prefix=settings.api_prefix,
        dependencies=protected_dep,
    )
    app.include_router(
        payment.router,
        prefix=settings.api_prefix,
        dependencies=protected_dep,
    )

    return app


# 全局应用实例
app = create_app()
