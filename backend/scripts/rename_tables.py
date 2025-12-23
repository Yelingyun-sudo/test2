#!/usr/bin/env python3
"""数据库表重命名迁移脚本

将表名修改为与路由名称一致：
- unsubscribed_tasks → evidence_tasks
- subscribed_tasks → subscription_tasks
- payment_tasks 保持不变
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# 确保可以导入 api 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.app.db import engine  # noqa: E402


def backup_database() -> None:
    """备份数据库文件"""
    db_path = Path(engine.url.database)
    backup_path = db_path.with_suffix('.db.backup')

    if not db_path.exists():
        raise SystemExit(f"数据库文件不存在: {db_path}")

    shutil.copy2(db_path, backup_path)
    print(f"✓ 数据库已备份到: {backup_path}")


def verify_tables_exist() -> bool:
    """验证原表是否存在"""
    with engine.begin() as conn:
        result = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('subscribed_tasks', 'unsubscribed_tasks', 'payment_tasks')"
        ).fetchall()

        existing_tables = {row[0] for row in result}
        print(f"✓ 检测到现有表: {existing_tables}")

        return 'subscribed_tasks' in existing_tables and 'unsubscribed_tasks' in existing_tables


def verify_new_tables_not_exist() -> bool:
    """验证新表名不存在（避免冲突）"""
    with engine.begin() as conn:
        result = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('subscription_tasks', 'evidence_tasks')"
        ).fetchall()

        if result:
            conflicting = {row[0] for row in result}
            print(f"✗ 警告：新表名已存在，会导致冲突: {conflicting}")
            return False

        return True


def rename_tables() -> None:
    """重命名表（核心步骤）"""
    with engine.begin() as conn:
        print("\n开始重命名表...")

        # 1. 重命名 unsubscribed_tasks → evidence_tasks
        conn.exec_driver_sql("ALTER TABLE unsubscribed_tasks RENAME TO evidence_tasks")
        print("✓ unsubscribed_tasks → evidence_tasks")

        # 2. 重命名 subscribed_tasks → subscription_tasks
        conn.exec_driver_sql("ALTER TABLE subscribed_tasks RENAME TO subscription_tasks")
        print("✓ subscribed_tasks → subscription_tasks")


def recreate_indexes() -> None:
    """重新创建唯一索引（使用新的命名约定）"""
    with engine.begin() as conn:
        print("\n重新创建索引...")

        # 删除旧索引（如果还存在）
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_tasks_url_account_date")
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_unsubscribed_url_date")
        print("✓ 已删除旧索引")

        # 创建新索引（subscription_tasks）
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_url_account_date "
            "ON subscription_tasks (url, account, created_date)"
        )
        print("✓ 创建索引: uq_subscription_url_account_date")

        # 创建新索引（evidence_tasks）
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_url_date "
            "ON evidence_tasks (url, created_date)"
        )
        print("✓ 创建索引: uq_evidence_url_date")


def verify_migration() -> None:
    """验证迁移结果"""
    with engine.begin() as conn:
        print("\n验证迁移结果...")

        # 验证表存在
        tables = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('subscription_tasks', 'evidence_tasks', 'payment_tasks')"
        ).fetchall()
        table_names = {row[0] for row in tables}

        assert 'subscription_tasks' in table_names, "subscription_tasks 表不存在"
        assert 'evidence_tasks' in table_names, "evidence_tasks 表不存在"
        assert 'payment_tasks' in table_names, "payment_tasks 表不存在"
        print(f"✓ 新表已创建: {table_names}")

        # 验证索引存在
        indexes = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name IN ('uq_subscription_url_account_date', 'uq_evidence_url_date')"
        ).fetchall()
        index_names = {row[0] for row in indexes}

        assert 'uq_subscription_url_account_date' in index_names
        assert 'uq_evidence_url_date' in index_names
        print(f"✓ 新索引已创建: {index_names}")

        # 验证数据完整性
        sub_count = conn.exec_driver_sql("SELECT COUNT(*) FROM subscription_tasks").scalar()
        evi_count = conn.exec_driver_sql("SELECT COUNT(*) FROM evidence_tasks").scalar()
        print(f"✓ 数据完整性: subscription_tasks={sub_count}行, evidence_tasks={evi_count}行")


def rollback_migration() -> None:
    """回滚迁移（恢复原表名）"""
    with engine.begin() as conn:
        print("\n开始回滚...")

        # 检查新表是否存在
        result = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('subscription_tasks', 'evidence_tasks')"
        ).fetchall()

        if not result:
            print("✗ 新表不存在，无法回滚（可能已经回滚过或未执行迁移）")
            return

        # 删除新索引
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_subscription_url_account_date")
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_evidence_url_date")

        # 恢复表名
        conn.exec_driver_sql("ALTER TABLE subscription_tasks RENAME TO subscribed_tasks")
        conn.exec_driver_sql("ALTER TABLE evidence_tasks RENAME TO unsubscribed_tasks")

        # 恢复旧索引
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_url_account_date "
            "ON subscribed_tasks (url, account, created_date)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_unsubscribed_url_date "
            "ON unsubscribed_tasks (url, created_date)"
        )

        print("✓ 回滚完成")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚迁移（恢复原表名）",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="跳过备份步骤（仅用于测试环境）",
    )
    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
        return

    # 正向迁移流程
    print("=" * 60)
    print("数据库表重命名迁移")
    print("=" * 60)

    # 1. 备份
    if not args.no_backup:
        backup_database()
    else:
        print("⚠️  已跳过备份步骤")

    # 2. 预检查
    if not verify_tables_exist():
        raise SystemExit("✗ 原表不存在，无法执行迁移")

    if not verify_new_tables_not_exist():
        raise SystemExit("✗ 新表名已存在，请先手动处理冲突")

    # 3. 执行迁移
    rename_tables()
    recreate_indexes()

    # 4. 验证
    verify_migration()

    print("\n" + "=" * 60)
    print("✓ 迁移完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. 运行 'make test' 验证功能")
    print("2. 启动应用检查是否正常")
    print("3. 如需回滚，执行: uv run python scripts/rename_tables.py --rollback")


if __name__ == "__main__":
    main()
