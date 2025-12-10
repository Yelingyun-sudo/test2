import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import auth, health, subscribed, unsubscribed
from .task_runner import run_task_loop
from website_analytics.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    app = FastAPI(title=settings.project_name)

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

    if settings.task_runner_enabled:
        @app.on_event("startup")
        async def _start_task_runner():
            app.state.task_runner = asyncio.create_task(run_task_loop())

        @app.on_event("shutdown")
        async def _stop_task_runner():
            task = getattr(app.state, "task_runner", None)
            if task:
                task.cancel()
                with contextlib.suppress(Exception):
                    await task

    return app


app = create_app()
