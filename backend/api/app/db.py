from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from website_analytics.settings import get_settings

Base = declarative_base()


def _prepare_sqlite_url(url: URL) -> tuple[URL, dict]:
    """确保 sqlite 路径为绝对路径并创建目录，同时配置连接参数。"""

    if url.drivername != "sqlite":
        return url, {}

    db_path = Path(url.database or "wa.db")
    if not db_path.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        db_path = (backend_root / db_path).resolve()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    return url.set(database=str(db_path)), {"check_same_thread": False}


def _configure_sqlite_pragmas(engine: Engine, url: URL) -> None:
    if url.drivername != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[unused-argument]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


def _create_engine() -> tuple[Engine, URL]:
    settings = get_settings()
    url = make_url(settings.database_url)
    url, connect_args = _prepare_sqlite_url(url)

    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    _configure_sqlite_pragmas(engine, url)
    return engine, url


engine, _engine_url = _create_engine()
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # 延迟导入以避免循环依赖
    from .models import user as user_model  # noqa: F401
    from .models import revoked_token as revoked_token_model  # noqa: F401
    from .models import subscription_task as subscription_task_model  # noqa: F401
    from .models import evidence_task as evidence_task_model  # noqa: F401
    from .models import payment_task as payment_task_model  # noqa: F401
    from .models import website as website_model  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_indices()
    _ensure_columns()
    _seed_admin_user()


def _ensure_indices() -> None:
    # 补充 SQLite 下的唯一索引（如果表已存在，create_all 不会自动新增）
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_url_account_date "
            "ON subscription_tasks (url, account, created_date)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_url_date "
            "ON evidence_tasks (url, created_date)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_url_date "
            "ON payment_tasks (url, created_date)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_websites_url ON websites (url)"
        )


def _ensure_columns() -> None:
    """确保关键新增列存在（针对已存在的 SQLite 数据库）。"""

    if _engine_url.drivername != "sqlite":
        return

    with engine.begin() as conn:
        # subscription_tasks 表的列迁移
        has_task_dir = conn.exec_driver_sql(
            "SELECT name FROM pragma_table_info('subscription_tasks') WHERE name='task_dir'"
        ).fetchone()
        if not has_task_dir:
            conn.exec_driver_sql(
                "ALTER TABLE subscription_tasks ADD COLUMN task_dir VARCHAR(1024)"
            )

        has_report_status = conn.exec_driver_sql(
            "SELECT name FROM pragma_table_info('subscription_tasks') WHERE name='report_status'"
        ).fetchone()
        if not has_report_status:
            conn.exec_driver_sql(
                "ALTER TABLE subscription_tasks ADD COLUMN report_status VARCHAR(16)"
            )

        has_llm_usage = conn.exec_driver_sql(
            "SELECT name FROM pragma_table_info('subscription_tasks') WHERE name='llm_usage'"
        ).fetchone()
        if not has_llm_usage:
            conn.exec_driver_sql(
                "ALTER TABLE subscription_tasks ADD COLUMN llm_usage JSON"
            )

        has_execution_count = conn.exec_driver_sql(
            "SELECT name FROM pragma_table_info('subscription_tasks') WHERE name='execution_count'"
        ).fetchone()
        if not has_execution_count:
            conn.exec_driver_sql(
                "ALTER TABLE subscription_tasks ADD COLUMN execution_count INTEGER DEFAULT 0 NOT NULL"
            )

        has_retry_at = conn.exec_driver_sql(
            "SELECT name FROM pragma_table_info('subscription_tasks') WHERE name='retry_at'"
        ).fetchone()
        if not has_retry_at:
            conn.exec_driver_sql(
                "ALTER TABLE subscription_tasks ADD COLUMN retry_at DATETIME"
            )

        # evidence_tasks 表的列迁移
        evidence_columns = {
            "status": "ALTER TABLE evidence_tasks ADD COLUMN status VARCHAR(16) DEFAULT 'PENDING' NOT NULL",
            "duration_seconds": "ALTER TABLE evidence_tasks ADD COLUMN duration_seconds INTEGER DEFAULT 0 NOT NULL",
            "executed_at": "ALTER TABLE evidence_tasks ADD COLUMN executed_at DATETIME",
            "task_dir": "ALTER TABLE evidence_tasks ADD COLUMN task_dir VARCHAR(1024)",
            "result": "ALTER TABLE evidence_tasks ADD COLUMN result TEXT",
            "failure_type": "ALTER TABLE evidence_tasks ADD COLUMN failure_type VARCHAR(255)",
            "report_status": "ALTER TABLE evidence_tasks ADD COLUMN report_status VARCHAR(16)",
            "llm_usage": "ALTER TABLE evidence_tasks ADD COLUMN llm_usage JSON",
        }

        for col_name, alter_sql in evidence_columns.items():
            has_column = conn.exec_driver_sql(
                f"SELECT name FROM pragma_table_info('evidence_tasks') WHERE name='{col_name}'"
            ).fetchone()
            if not has_column:
                conn.exec_driver_sql(alter_sql)

        # payment_tasks 表的列迁移
        payment_columns = {
            "account": "ALTER TABLE payment_tasks ADD COLUMN account VARCHAR(255) NOT NULL DEFAULT ''",
            "password": "ALTER TABLE payment_tasks ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT ''",
            "status": "ALTER TABLE payment_tasks ADD COLUMN status VARCHAR(16) DEFAULT 'PENDING' NOT NULL",
            "duration_seconds": "ALTER TABLE payment_tasks ADD COLUMN duration_seconds INTEGER DEFAULT 0 NOT NULL",
            "executed_at": "ALTER TABLE payment_tasks ADD COLUMN executed_at DATETIME",
            "task_dir": "ALTER TABLE payment_tasks ADD COLUMN task_dir VARCHAR(1024)",
            "result": "ALTER TABLE payment_tasks ADD COLUMN result TEXT",
            "failure_type": "ALTER TABLE payment_tasks ADD COLUMN failure_type VARCHAR(255)",
            "report_status": "ALTER TABLE payment_tasks ADD COLUMN report_status VARCHAR(16)",
            "llm_usage": "ALTER TABLE payment_tasks ADD COLUMN llm_usage JSON",
        }

        for col_name, alter_sql in payment_columns.items():
            has_column = conn.exec_driver_sql(
                f"SELECT name FROM pragma_table_info('payment_tasks') WHERE name='{col_name}'"
            ).fetchone()
            if not has_column:
                conn.exec_driver_sql(alter_sql)


def _seed_admin_user() -> None:
    """按环境变量播种管理员账号（幂等）。"""

    settings = get_settings()
    if not settings.admin_seed_username or not settings.admin_seed_password:
        return

    from .repositories.users import (
        get_user_by_username,
        normalize_username,
        create_user,
    )
    from .security import get_password_hash

    username = normalize_username(settings.admin_seed_username)
    password_hash = get_password_hash(settings.admin_seed_password)

    session = SessionLocal()
    try:
        user = get_user_by_username(session, username)
        if user:
            user.password_hash = password_hash
            user.is_admin = True
            user.is_active = True
            session.add(user)
            session.commit()
        else:
            create_user(
                session,
                username=username,
                password_hash=password_hash,
                is_admin=True,
                is_active=True,
            )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
