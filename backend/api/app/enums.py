"""通用枚举类型定义。"""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    """任务执行状态。"""

    PENDING = "PENDING"  # 待执行
    RUNNING = "RUNNING"  # 执行中
    RETRYING = "RETRYING"  # 等待重试
    SUCCESS = "SUCCESS"  # 成功
    FAILED = "FAILED"  # 失败


class TaskReportStatus(str, Enum):
    """任务汇报状态。"""

    PENDING = "PENDING"  # 待汇报（任务已完成，等待发送）
    SUCCESS = "SUCCESS"  # Kafka 发送成功
    FAILED = "FAILED"  # Kafka 发送失败
