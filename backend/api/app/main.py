from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, health, subscribed, unsubscribed
from website_analytics.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
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
    return app


app = create_app()
