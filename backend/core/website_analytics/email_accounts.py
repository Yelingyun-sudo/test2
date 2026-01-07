"""邮箱账号管理模块

提供多邮箱账号的配置加载、选择和管理功能。
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List

import yaml

from .models import EmailAccount


class EmailAccountManager:
    """邮箱账号管理器

    负责从配置文件加载多个邮箱账号，并提供账号选择功能。
    """

    def __init__(self, config_file: Path):
        """初始化账号管理器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.accounts: List[EmailAccount] = []
        self._load_accounts()

    def _load_accounts(self) -> None:
        """从配置文件加载账号列表

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: 配置文件格式错误
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"邮箱账号配置文件不存在: {self.config_file}")

        with open(self.config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 只加载启用的账号
        raw_accounts = data.get("accounts", [])
        self.accounts = [
            EmailAccount(**acc) for acc in raw_accounts if acc.get("enabled", True)
        ]

    def get_random_account(self) -> EmailAccount | None:
        """随机选择一个启用的账号

        Returns:
            随机选中的账号，无可用账号时返回 None
        """
        if not self.accounts:
            return None
        return random.choice(self.accounts)

    def get_account_by_email(self, email: str) -> EmailAccount | None:
        """根据邮箱地址查找账号

        Args:
            email: 邮箱地址

        Returns:
            匹配的账号，未找到时返回 None
        """
        for acc in self.accounts:
            if acc.register_account == email:
                return acc
        return None

    def reload(self) -> None:
        """重新加载配置文件

        用于动态更新账号列表，无需重启服务。
        """
        self.accounts.clear()
        self._load_accounts()


# 全局单例
_manager: EmailAccountManager | None = None


def get_account_manager() -> EmailAccountManager:
    """获取账号管理器单例

    Returns:
        账号管理器实例
    """
    global _manager
    if _manager is None:
        # 配置文件路径：backend/email_accounts.yaml
        config_file = Path(__file__).parent.parent.parent / "email_accounts.yaml"
        _manager = EmailAccountManager(config_file)
    return _manager


def get_random_email_account() -> EmailAccount | None:
    """获取随机邮箱账号（便捷函数）

    Returns:
        随机选中的账号，无可用账号时返回 None
    """
    return get_account_manager().get_random_account()
