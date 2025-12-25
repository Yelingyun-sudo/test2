import asyncio
import contextlib
import logging
import logging.config
from contextlib import asynccontextmanager

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
    },
    "root": {
        "level": "INFO",
        "handlers": ["default"],
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "httpx": {"level": "WARNING"},
        "kafka": {"level": "WARNING"},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # 启动逻辑
    if settings.task_runner_enabled:
        app.state.subscription_runner = asyncio.create_task(
            run_subscription_runner_loop()
        )
        app.state.evidence_runner = asyncio.create_task(run_evidence_runner_loop())
    if settings.task_cleaner_enabled:
        app.state.task_cleaner = asyncio.create_task(run_task_cleaner_loop())
    if settings.task_importer_enabled:
        app.state.task_importer = asyncio.create_task(run_task_importer_loop())
    if settings.task_reporter_enabled:
        app.state.task_reporter = asyncio.create_task(run_task_reporter_loop())

    yield

    # 关闭逻辑
    if settings.task_runner_enabled:
        task = getattr(app.state, "subscription_runner", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await task
        task = getattr(app.state, "evidence_runner", None)
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


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    app = FastAPI(title=settings.project_name, lifespan=lifespan)

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


app = create_app()
