"""数据模型定义

定义系统中使用的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EmailAccount:
    """邮箱账号配置

    Attributes:
        register_account: 注册使用的邮箱地址（同时作为账号标识）
        register_password: 注册密码
        imap_server: IMAP 服务器地址
        imap_port: IMAP 端口
        imap_username: IMAP 登录用户名
        imap_password: IMAP 登录密码（授权码）
        enabled: 是否启用该账号
    """

    register_account: str
    register_password: str
    imap_server: str
    imap_port: int
    imap_username: str
    imap_password: str
    enabled: bool = True
