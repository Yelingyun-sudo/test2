from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..models.website import Website, WebsiteStatus


def sync_credential_from_subscription_task(
    db: Session,
    url: str,
    account: str,
    password: str,
) -> None:
    """将 SubscriptionTask 的账号信息同步到 websites 表

    Args:
        db: 数据库会话
        url: 网站 URL
        account: 账号
        password: 密码

    逻辑:
        1. 如果 URL 不存在，创建新 website 记录，添加第一个账号
        2. 如果 URL 存在：
           - 如果 account 已存在，更新 password 和 created_at
           - 如果 account 不存在，追加新账号
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 查找现有记录
    website = db.query(Website).filter_by(url=url).first()

    if not website:
        # 创建新记录
        website = Website(
            url=url,
            credentials=[
                {
                    "account": account,
                    "password": password,
                    "source": "SubscriptionTask",
                    "created_at": now,
                }
            ],
            status=WebsiteStatus.INITIALIZED,
        )
        db.add(website)
        db.commit()
        return

    # 更新现有记录
    credentials = website.credentials or []
    account_found = False

    # 查找是否存在相同 account
    for cred in credentials:
        if cred.get("account") == account:
            # 更新现有账号
            cred["password"] = password
            cred["created_at"] = now
            account_found = True
            break

    if not account_found:
        # 追加新账号
        credentials.append(
            {
                "account": account,
                "password": password,
                "source": "SubscriptionTask",
                "created_at": now,
            }
        )

    website.credentials = credentials
    flag_modified(website, "credentials")
    db.commit()
