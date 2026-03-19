from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar, Union

from pydantic import ValidationError
from sqlalchemy import Integer, and_, case, func, text
from sqlalchemy.orm import Session

from ..enums import TaskStatus
from ..models import EvidenceTask, SubscriptionTask
from ..schemas.common import (
    FailureTypeItem,
    FailureTypesResponse,
    LLMUsage,
    TaskStatsSummary,
)
from ..schemas.evidence import EvidenceItem
from ..schemas.subscription import SubscriptionItem
from website_analytics.output_types import (
    FAILURE_TYPE_LABELS,
    get_failure_types_ordered,
)

logger = logging.getLogger(__name__)

# 类型变量，用于泛型函数
TaskModel = TypeVar("TaskModel")
ItemModel = TypeVar("ItemModel")


def parse_date_range(
    start_date: str | None,
    end_date: str | None,
    tz_cn: timezone,
) -> tuple[datetime | None, datetime | None]:
    """
    解析日期范围，返回 UTC 时区的 (开始时间, 结束时间)

    Args:
        start_date: 开始日期 YYYY-MM-DD 格式
        end_date: 结束日期 YYYY-MM-DD 格式
        tz_cn: 中国时区

    Returns:
        (start_time_utc, end_time_utc) 或 (None, None)

    Note:
        内部先计算东八区的时间范围，然后转换为 UTC 返回。
        这样可以确保与数据库中存储的 UTC 时间正确比较。
    """
    if not start_date or not end_date:
        return None, None

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        start = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz_cn)
        end = datetime.strptime(end_date, "%Y-%m-%d")
        end = end.replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz_cn
        )
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    except ValueError:
        # 日期格式无效
        return None, None


def format_datetime(dt: datetime | None, tz_cn: timezone) -> str:
    """
    格式化日期时间为 ISO 字符串

    Args:
        dt: 日期时间对象（可以是 None）
        tz_cn: 中国时区

    Returns:
        ISO 格式字符串，如果 dt 为 None 则返回空字符串
    """
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz_cn).isoformat()


def compute_status_distribution(
    db: Session,
    task_model: type[TaskModel],
    start_date: str | None,
    end_date: str | None,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
    status_distribution_item_cls: type,
) -> list:
    """
    计算状态分布（根据时间范围过滤）

    Args:
        db: 数据库会话
        task_model: 任务模型类（EvidenceTask 或 SubscriptionTask）
        start_date: 开始日期字符串
        end_date: 结束日期字符串
        range_start_utc: UTC 开始时间（None 表示不应用日期过滤）
        range_end_utc: UTC 结束时间（None 表示不应用日期过滤）
        status_distribution_item_cls: StatusDistributionItem 类

    Returns:
        状态分布列表
    """
    status_query = db.query(
        task_model.status.label("status"),
        func.count(task_model.id).label("count"),
    )

    # 应用时间范围过滤（如果指定且有效）
    if (
        start_date
        and end_date
        and range_start_utc is not None
        and range_end_utc is not None
    ):
        status_query = status_query.filter(
            task_model.executed_at.isnot(None),
            task_model.executed_at >= range_start_utc,
            task_model.executed_at <= range_end_utc,
        )

    status_results = status_query.group_by(task_model.status).all()

    status_distribution = []
    for row in status_results:
        status_value = row.status.value if hasattr(row.status, "value") else row.status
        status_distribution.append(
            status_distribution_item_cls(
                status=status_value or "", count=row.count or 0
            )
        )

    return status_distribution


def compute_failure_stats(
    db: Session,
    task_model: type[TaskModel],
    start_date: str | None,
    end_date: str | None,
    tz_cn: timezone,
    failure_type_distribution_item_cls: type,
    failure_summary_cls: type,
) -> tuple[list, object]:
    """
    计算失败类型分布统计和失败总览（支持时间范围过滤）

    Args:
        db: 数据库会话
        task_model: 任务模型类（EvidenceTask 或 SubscriptionTask）
        start_date: 开始日期字符串
        end_date: 结束日期字符串
        tz_cn: 中国时区
        failure_type_distribution_item_cls: FailureTypeDistributionItem 类
        failure_summary_cls: FailureSummary 类

    Returns:
        (失败类型分布列表, 失败总览对象)
    """
    from ..enums import TaskStatus

    failure_type_query = db.query(
        task_model.failure_type,
        func.count(task_model.id).label("count"),
    ).filter(
        task_model.status == TaskStatus.FAILED,
        task_model.failure_type.isnot(None),
    )

    # 应用时间范围过滤（如果指定）
    if start_date and end_date:
        start_time, end_time = parse_date_range(start_date, end_date, tz_cn)
        if start_time and end_time:
            failure_type_query = failure_type_query.filter(
                task_model.executed_at.isnot(None),
                task_model.executed_at >= start_time,
                task_model.executed_at <= end_time,
            )

    failure_type_results = (
        failure_type_query.group_by(task_model.failure_type)
        .order_by(func.count(task_model.id).desc())
        .all()
    )

    # 计算时间范围内的实际失败总数（用于百分比计算）
    range_failed_count = sum(row.count or 0 for row in failure_type_results)

    # Top 5 + "其他"
    top_5_types = failure_type_results[:5]
    others_count = sum(row.count or 0 for row in failure_type_results[5:])

    failure_type_distribution = []
    for row in top_5_types:
        count = row.count or 0
        # 使用时间范围内的失败数计算百分比
        percentage = (
            (count / range_failed_count * 100) if range_failed_count > 0 else 0.0
        )
        failure_type_distribution.append(
            failure_type_distribution_item_cls(
                type=row.failure_type or "",
                label=FAILURE_TYPE_LABELS.get(
                    row.failure_type or "", row.failure_type or ""
                ),
                count=count,
                percentage=round(percentage, 1),
            )
        )

    # 添加"其他"类别
    if others_count > 0:
        others_percentage = (
            (others_count / range_failed_count * 100) if range_failed_count > 0 else 0.0
        )
        failure_type_distribution.append(
            failure_type_distribution_item_cls(
                type="others",
                label="其他",
                count=others_count,
                percentage=round(others_percentage, 1),
            )
        )

    failure_summary = failure_summary_cls(
        total_failed=range_failed_count,  # 使用时间范围内的数量
        unique_types=len(failure_type_results),
    )

    return failure_type_distribution, failure_summary


def compute_daily_trend(
    db: Session,
    task_model: type[TaskModel],
    tz_cn: timezone,
    days: int,
    daily_trend_item_cls: type,
) -> list:
    """
    计算每日趋势

    Args:
        db: 数据库会话
        task_model: 任务模型类（EvidenceTask 或 SubscriptionTask）
        tz_cn: 中国时区
        days: 计算最近多少天（例如：5 表示最近5天）
        daily_trend_item_cls: DailyTrendItem 类

    Returns:
        每日趋势列表
    """
    from ..enums import TaskStatus

    now_cn = datetime.now(tz_cn)
    days_ago = now_cn.date() - timedelta(days=days - 1)

    # 按执行时间的日期分组（转换为中国时区后提取日期）
    # 使用 date(datetime(executed_at, '+8 hours')) 将 UTC 时间转换为中国时区后提取日期
    date_cn_expr = func.date(func.datetime(task_model.executed_at, text("'+8 hours'")))

    daily_trend_results = (
        db.query(
            date_cn_expr.label("date"),
            func.count(task_model.id).label("total_count"),
            func.sum(case((task_model.status == TaskStatus.SUCCESS, 1), else_=0)).label(
                "success_count"
            ),
            func.sum(case((task_model.status == TaskStatus.FAILED, 1), else_=0)).label(
                "failed_count"
            ),
        )
        .filter(
            task_model.executed_at.isnot(None),
            task_model.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]),
            date_cn_expr >= days_ago,
        )
        .group_by(date_cn_expr)
        .order_by(date_cn_expr.asc())
        .all()
    )

    daily_trend = []
    for row in daily_trend_results:
        total_count = row.total_count or 0
        success_count_day = row.success_count or 0
        failed_count_day = row.failed_count or 0
        completed_day = success_count_day + failed_count_day
        day_success_rate = (
            (success_count_day / completed_day) if completed_day > 0 else 0.0
        )

        # 处理 row.date 可能是字符串或 date 对象的情况
        date_str = ""
        if row.date:
            if isinstance(row.date, str):
                date_str = row.date
            else:
                date_str = row.date.isoformat()

        daily_trend.append(
            daily_trend_item_cls(
                date=date_str,
                total_count=total_count,
                success_count=success_count_day,
                failed_count=failed_count_day,
                success_rate=day_success_rate,
            )
        )

    return daily_trend


def compute_recent_tasks(
    db: Session,
    task_model: type[TaskModel],
    start_date: str | None,
    end_date: str | None,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
    tz_cn: timezone,
    item_cls: type,
    build_item_fn: Callable,
) -> list:
    """
    获取最新任务列表

    Args:
        db: 数据库会话
        task_model: 任务模型类（EvidenceTask 或 SubscriptionTask）
        start_date: 开始日期字符串
        end_date: 结束日期字符串
        range_start_utc: UTC 开始时间（None 表示不应用日期过滤）
        range_end_utc: UTC 结束时间（None 表示不应用日期过滤）
        tz_cn: 中国时区
        item_cls: Item 类（EvidenceItem 或 SubscriptionItem）
        build_item_fn: 构建 Item 对象的函数，接收 (rec, _format_dt) 参数

    Returns:
        最新任务列表（最多 100 条）
    """
    from ..enums import TaskStatus

    def _format_dt(dt):
        return format_datetime(dt, tz_cn)

    # 状态优先级：running > success/failed > pending
    recent_status_priority = case(
        (task_model.status == TaskStatus.RUNNING, 0),
        (task_model.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED]), 1),
        else_=2,
    )

    recent_task_query = db.query(task_model)

    # 应用时间范围过滤（如果指定且有效）
    if (
        start_date
        and end_date
        and range_start_utc is not None
        and range_end_utc is not None
    ):
        recent_task_query = recent_task_query.filter(
            task_model.executed_at.isnot(None),
            task_model.executed_at >= range_start_utc,
            task_model.executed_at <= range_end_utc,
        )

    recent_task_records = (
        recent_task_query.order_by(
            recent_status_priority,
            task_model.executed_at.desc().nulls_last(),
            task_model.id.asc(),
        )
        .limit(100)
        .all()
    )

    recent_tasks = []
    for rec in recent_task_records:
        recent_tasks.append(build_item_fn(rec, _format_dt))

    return recent_tasks


def get_failure_types_endpoint() -> FailureTypesResponse:
    """
    获取所有失败类型及其中文标签，按业务优先级排序。

    Returns:
        失败类型列表，包含 value 和 label 字段。
    """
    types_list = get_failure_types_ordered()
    return FailureTypesResponse(items=[FailureTypeItem(**item) for item in types_list])


def build_time_range_conditions(
    task_model: type,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
) -> list:
    """构建时间范围过滤条件"""
    if range_start_utc is not None and range_end_utc is not None:
        return [
            task_model.executed_at >= range_start_utc,
            task_model.executed_at <= range_end_utc,
        ]
    return []


def build_tokens_count_expr(task_model: type, time_range_conditions: list):
    """构建 tokens 计数表达式（带时间范围过滤）"""
    tokens_conditions = [task_model.executed_at.isnot(None)]
    if time_range_conditions:
        tokens_conditions.extend(time_range_conditions)

    return case(
        (
            and_(*tokens_conditions),
            func.coalesce(
                func.cast(
                    func.json_extract(task_model.llm_usage, "$.total_tokens"),
                    Integer,
                ),
                0,
            ),
        ),
        else_=0,
    )


def build_status_count_expr(
    task_model: type, status: object, time_range_conditions: list
):
    """构建状态计数表达式（带时间范围过滤）"""

    status_conditions = [
        task_model.executed_at.isnot(None),
        task_model.status == status,
    ]
    if time_range_conditions:
        status_conditions.extend(time_range_conditions)

    return case((and_(*status_conditions), 1), else_=0)


def build_duration_avg_expr(
    task_model: type, status: object, time_range_conditions: list
):
    """构建时长平均值表达式（带时间范围过滤）"""

    duration_conditions = [
        task_model.executed_at.isnot(None),
        task_model.status == status,
    ]
    if time_range_conditions:
        duration_conditions.extend(time_range_conditions)

    return case((and_(*duration_conditions), task_model.duration_seconds), else_=None)


def build_tokens_avg_expr(
    task_model: type, status: object, time_range_conditions: list
):
    """构建 tokens 平均值表达式（带时间范围过滤）"""

    tokens_conditions = [
        task_model.executed_at.isnot(None),
        task_model.status == status,
    ]
    if time_range_conditions:
        tokens_conditions.extend(time_range_conditions)

    return case(
        (
            and_(*tokens_conditions),
            func.cast(
                func.json_extract(task_model.llm_usage, "$.total_tokens"),
                Integer,
            ),
        ),
        else_=None,
    )


def should_zero_pending_running(
    range_end_utc: datetime | None, tz_cn: timezone
) -> bool:
    """判断是否应该将 pending 和 running 计数清零"""
    if range_end_utc is None:
        return False

    now_cn = datetime.now(tz_cn)
    today_end_cn = now_cn.replace(hour=23, minute=59, second=59, microsecond=999999)
    today_end_utc = today_end_cn.astimezone(timezone.utc)

    return range_end_utc < today_end_utc


def compute_task_summary(
    db: Session,
    task_model: type,
    range_start_utc: datetime | None,
    range_end_utc: datetime | None,
    tz_cn: timezone,
) -> TaskStatsSummary:
    """
    计算任务统计汇总（通用函数）

    Args:
        db: 数据库会话
        task_model: 任务模型类（SubscriptionTask 或 EvidenceTask）
        range_start_utc: 开始时间（UTC）
        range_end_utc: 结束时间（UTC）
        tz_cn: 中国时区

    Returns:
        TaskStatsSummary: 统计汇总
    """
    # 构建时间范围条件
    time_range_conditions = build_time_range_conditions(
        task_model, range_start_utc, range_end_utc
    )

    # 构建各种 case 表达式
    success_count_expr = build_status_count_expr(
        task_model, TaskStatus.SUCCESS, time_range_conditions
    )
    failed_count_expr = build_status_count_expr(
        task_model, TaskStatus.FAILED, time_range_conditions
    )
    tokens_expr = build_tokens_count_expr(task_model, time_range_conditions)
    success_tokens_avg_expr = build_tokens_avg_expr(
        task_model, TaskStatus.SUCCESS, time_range_conditions
    )
    failed_tokens_avg_expr = build_tokens_avg_expr(
        task_model, TaskStatus.FAILED, time_range_conditions
    )
    success_duration_avg_expr = build_duration_avg_expr(
        task_model, TaskStatus.SUCCESS, time_range_conditions
    )
    failed_duration_avg_expr = build_duration_avg_expr(
        task_model, TaskStatus.FAILED, time_range_conditions
    )

    # 执行查询
    summary_result = db.query(
        func.sum(case((task_model.status == TaskStatus.PENDING, 1), else_=0)).label(
            "pending_count"
        ),
        func.sum(case((task_model.status == TaskStatus.RUNNING, 1), else_=0)).label(
            "running_count"
        ),
        func.sum(success_count_expr).label("today_success_count"),
        func.sum(failed_count_expr).label("today_failed_count"),
        func.sum(tokens_expr).label("today_tokens"),
        func.avg(success_tokens_avg_expr).label("today_avg_success_tokens"),
        func.avg(failed_tokens_avg_expr).label("today_avg_failed_tokens"),
        func.avg(success_duration_avg_expr).label("today_avg_success_duration"),
        func.avg(failed_duration_avg_expr).label("today_avg_failed_duration"),
    ).first()

    # 处理结果
    pending_count = summary_result.pending_count or 0
    running_count = summary_result.running_count or 0
    today_success_count = summary_result.today_success_count or 0
    today_failed_count = summary_result.today_failed_count or 0

    # 历史时间范围内，pending/running 应该为 0
    if should_zero_pending_running(range_end_utc, tz_cn):
        pending_count = 0
        running_count = 0

    total_tasks = today_success_count + today_failed_count
    today_tokens = summary_result.today_tokens or 0
    today_avg_success_tokens = summary_result.today_avg_success_tokens or 0.0
    today_avg_failed_tokens = summary_result.today_avg_failed_tokens or 0.0
    today_avg_success_duration = summary_result.today_avg_success_duration or 0.0
    today_avg_failed_duration = summary_result.today_avg_failed_duration or 0.0

    return TaskStatsSummary(
        total_tasks=total_tasks,
        pending_count=pending_count,
        running_count=running_count,
        today_success_count=today_success_count,
        today_failed_count=today_failed_count,
        today_tokens=today_tokens,
        today_avg_success_tokens=today_avg_success_tokens,
        today_avg_failed_tokens=today_avg_failed_tokens,
        today_avg_success_duration_seconds=today_avg_success_duration,
        today_avg_failed_duration_seconds=today_avg_failed_duration,
    )


def build_task_item(
    rec: Union[SubscriptionTask, EvidenceTask],
    item_cls: type[Union[SubscriptionItem, EvidenceItem]],
    format_dt: Callable[[datetime | None], str],
) -> Union[SubscriptionItem, EvidenceItem]:
    """
    通用任务 Item 构建函数

    用于将数据库任务记录（SubscriptionTask 或 EvidenceTask）转换为对应的响应模型
    （SubscriptionItem 或 EvidenceItem）。

    Args:
        rec: 任务数据库记录，可以是 SubscriptionTask 或 EvidenceTask
        item_cls: Item 类，可以是 SubscriptionItem 或 EvidenceItem
        format_dt: 日期时间格式化函数，接受 datetime | None，返回 ISO 格式字符串

    Returns:
        构建的 Item 对象（SubscriptionItem 或 EvidenceItem）

    Raises:
        ValidationError: 当 llm_usage 数据格式错误时，会记录错误日志但不会抛出异常
        TypeError: 当 llm_usage 数据格式错误时，会记录错误日志但不会抛出异常
    """
    status_value = rec.status.value if hasattr(rec.status, "value") else rec.status

    # 安全地转换 llm_usage
    llm_usage_value = None
    if rec.llm_usage is not None:
        try:
            llm_usage_value = LLMUsage(**rec.llm_usage)
        except (ValidationError, TypeError) as exc:
            logger.error(
                "任务 ID=%s 的 llm_usage 数据格式错误，已跳过: %s",
                rec.id,
                exc,
            )

    return item_cls(
        id=int(rec.id) if rec.id is not None else 0,
        url=rec.url,
        account=rec.account,
        password=rec.password,
        status=status_value or "",
        created_at=format_dt(rec.created_at),
        duration_seconds=rec.duration_seconds or 0,
        executed_at=format_dt(rec.executed_at),
        task_dir=rec.task_dir,
        result=rec.result,
        failure_type=rec.failure_type,
        llm_usage=llm_usage_value,
    )
