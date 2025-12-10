import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import auth, health, subscribed, unsubscribed
from .task_cleaner import run_task_cleaner_loop
from .task_runner import run_task_loop
from website_analytics.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # 启动逻辑
    if settings.task_runner_enabled:
        app.state.task_runner = asyncio.create_task(run_task_loop())
    if settings.task_cleaner_enabled:
        app.state.task_cleaner = asyncio.create_task(run_task_cleaner_loop())

    yield

    # 关闭逻辑
    if settings.task_runner_enabled:
        task = getattr(app.state, "task_runner", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception):
                await task
    if settings.task_cleaner_enabled:
        task = getattr(app.state, "task_cleaner", None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception):
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
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(subscribed.router, prefix=settings.api_prefix)
    app.include_router(unsubscribed.router, prefix=settings.api_prefix)

    return app


app = create_app()
