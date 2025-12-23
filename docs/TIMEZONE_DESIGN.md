# 时区处理设计文档

## 核心策略

本项目采用 **"UTC 存储，业务层转换"** 策略：

1. **存储层**：所有 `DateTime` 字段存储 UTC 时间
2. **计算层**：时间范围、日期计算使用东八区（UTC+8）
3. **查询层**：过滤条件转换为 UTC 后查询
4. **展示层**：返回前端时转换为东八区 ISO 格式

## 时区常量

所有时区相关代码统一使用 `backend/api/app/constants.py` 中的常量：

```python
from datetime import timedelta, timezone

TZ_CHINA = timezone(timedelta(hours=8))
```

## 数据库字段设计

### `created_at` vs `created_date`

- **`created_at`**（DateTime）：精确的创建时间戳，存储 UTC 时间
  - 用途：审计、排序、精确时间记录
  
- **`created_date`**（Date）：业务日期，存储东八区日期
  - 用途：唯一性约束、按日分组统计、索引优化
  - **不是冗余字段**，有独立的业务价值

### `executed_at`（DateTime）

执行时间，存储 UTC 时间。

**重要**：首页"今日"统计基于 `executed_at` 而不是 `created_date`，因为业务语义是"今日执行情况"。

## 时间范围过滤的正确实现

### 关键点：先东八区计算，再转UTC比较

```python
# 1. 计算东八区的时间范围
tz_cn = timezone(timedelta(hours=8))
now_cn = datetime.now(tz_cn)
today_start_cn = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)
today_end_cn = now_cn.replace(hour=23, minute=59, second=59, microsecond=999999)

# 2. 转换为 UTC
today_start_utc = today_start_cn.astimezone(timezone.utc)
today_end_utc = today_end_cn.astimezone(timezone.utc)

# 3. 用 UTC 时间与数据库比较
query.filter(
    Task.executed_at >= today_start_utc,
    Task.executed_at <= today_end_utc,
)
```

### 时间映射关系

| 东八区时间 | UTC 时间 |
|-----------|----------|
| 2025-12-23 00:00:00+08:00 | 2025-12-22 16:00:00+00:00 |
| 2025-12-23 08:00:00+08:00 | 2025-12-23 00:00:00+00:00 |
| 2025-12-23 23:59:59+08:00 | 2025-12-23 15:59:59+00:00 |

**结论**：东八区的"今日"对应 UTC 的"昨日16:00 到今日15:59"

## 常见陷阱

### ❌ 错误做法1：直接用东八区时间比较

```python
# 错误！数据库存的是UTC，这样比较会错8小时
today_start_cn = now_cn.replace(hour=0, ...)
query.filter(Task.executed_at >= today_start_cn)
```

### ❌ 错误做法2：使用本地时区

```python
# 错误！服务器时区不确定
start_time = datetime.now()
```

### ✅ 正确做法：明确时区转换

```python
# 正确！业务逻辑在东八区，存储和比较在UTC
today_start_cn = datetime.now(TZ_CHINA).replace(hour=0, ...)
today_start_utc = today_start_cn.astimezone(timezone.utc)
query.filter(Task.executed_at >= today_start_utc)
```

## 前端时间处理

前端使用 `Intl.DateTimeFormat` 明确指定时区：

```typescript
// frontend/lib/datetime.ts
const formatter = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",  // 明确指定东八区
  // ...
});
```

后端返回的 ISO 格式时间字符串会自动转换为东八区显示。

## 测试验证

### 边界时间测试

在东八区 00:00 前后测试，确认：
- 东八区 23:59 的任务算"今日"
- 东八区 00:00 的任务算"今日"
- UTC 16:00（对应东八区次日00:00）不算"今日"

### 跨时区测试

在不同时区的服务器上测试，确认行为一致。

## 开发注意事项

1. **新增时间字段**：必须使用 `DateTime(timezone=True)` 并存储 UTC
2. **时间范围查询**：参考 `_parse_time_range` 函数的实现
3. **避免 `datetime.now()`**：必须明确指定时区参数
4. **统计查询**：明确是基于创建时间还是执行时间

## 相关文件

- `backend/api/app/constants.py` - 时区常量定义
- `backend/api/app/routers/subscribed.py` - 时间范围过滤实现
- `backend/api/app/models/subscribed_task.py` - 数据模型定义
- `frontend/lib/datetime.ts` - 前端时间格式化

---

**最后更新**：2025-12-23

