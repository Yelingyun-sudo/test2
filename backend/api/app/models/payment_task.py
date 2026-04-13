from __future__ import annotations

"""SQLAlchemy 模型，定义支付任务表结构"""
"""文件定义了 支付任务的数据模型（PaymentTask），用于在数据库中存储和管理支付相关的自动化任务。它是 SQLAlchemy ORM 模型，映射到 payment_tasks 表。"""
# 把数据库表映射成 Python 类，把行映射成对象,开发者可以用面向对象的方式操作数据库，无需手写 SQL
# 将数据库表抽象为 Python 对象，同时整合数据结构定义、约束校验、业务逻辑、关系管理和迁移控制，形成一个统一、安全、可维护的数据访问层。
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ..constants import TZ_CHINA
from ..db import Base
from ..enums import TaskReportStatus, TaskStatus


class PaymentTask(Base):
    """支付任务模型，用于存储从 Kafka 接收的支付任务"""

    __tablename__ = "payment_tasks"  # 显式指定了该模型对应的数据库表名为 payment_tasks  每个模型类都继承自一个 基类（Base），这个基类是由 declarative_base() 生成的。基类内部维护了一个 MetaData 对象，记录所有模型与数据库表的映射关系。
    __table_args__ = (
        # 同一 URL 每天只能创建一个任务，避免重复
        UniqueConstraint("url", "created_date", name="uq_payment_url_date"),
    )

    # ===== 基础字段 =====
    id = Column(
        Integer, primary_key=True, index=True
    )  # 主键，自增整数，用于唯一标识一条任务记录。
    url = Column(String(2048), nullable=False, index=True, comment="支付页面 URL")
    account = Column(String(255), nullable=False, comment="登录账号")
    password = Column(String(255), nullable=False, comment="登录密码")

    # ===== 执行状态字段 =====
    # status：枚举类型（TaskStatus），取值：PENDING（待处理）、RUNNING（执行中）、SUCCESS（成功）、FAILED（失败）。默认 PENDING。
    status = Column(
        SAEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
        comment="任务状态：PENDING/RUNNING/SUCCESS/FAILED",
    )
    duration_seconds = Column(
        Integer, nullable=False, default=0, comment="执行耗时（秒）"
    )  # 任务实际执行耗时（整数秒），默认 0。
    executed_at = Column(
        DateTime(timezone=True), nullable=True, comment="实际开始执行时间"
    )  # 实际开始执行的时间（带时区的 DateTime），可为空
    task_dir = Column(
        String(1024), nullable=True, comment="任务执行产生的文件目录"
    )  # 任务执行时生成的工作目录路径（相对项目根目录），用于存储截图、日志、视频等产物。

    # ===== 结果字段 =====
    result = Column(Text, nullable=True, comment="任务执行结果（成功时存储支付码信息）")
    failure_type = Column(
        String(255), nullable=True, comment="失败类型（如 task_timeout）"
    )
    # report_status：报告生成状态（TaskReportStatus 枚举），可选值：PENDING、SUCCESS、FAILED，表示该任务对应的报告是否已生成。可为空。
    report_status = Column(
        SAEnum(TaskReportStatus),
        nullable=True,
        default=None,
        comment="报告状态：PENDING/SUCCESS/FAILED",
    )

    # ===== LLM Token 统计 =====
    llm_usage = Column(JSON, nullable=True, comment="LLM token 使用统计")

    # ===== 时间字段 =====
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="任务创建时间",
    )
    # 仅日期部分，用于去重约束（同一 URL 每天只允许创建一条任务），默认使用中国时区（TZ_CHINA）的当前日期。
    created_date = Column(
        Date,
        nullable=False,
        default=lambda: datetime.now(TZ_CHINA).date(),
        comment="任务创建日期（用于去重）",
    )

    def __repr__(self) -> str:
        return f"<PaymentTask id={self.id} url={self.url}>"
