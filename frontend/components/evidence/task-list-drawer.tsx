"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";

// DashboardShell removed - this component is used inside a Sheet
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DateRangePicker, type DateRange } from "@/components/ui/date-range-picker";
import { format } from "date-fns";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatDurationSeconds } from "@/lib/datetime";
import { cn } from "@/lib/utils";
import { TaskDetailModal } from "./task-detail-modal";
import type { EvidenceItem } from "@/types/evidence";
import {
  STATUS_LABELS,
  STATUS_STYLES,
  type TaskStatus,
  type FailureTypeItem,
} from "@/types/common";

const PAGE_SIZE = 15;

type EvidenceContentProps = {
  failureTypes: FailureTypeItem[];
  failureTypeLabel: Record<string, string>;
};

function EvidenceContent({ failureTypes, failureTypeLabel }: EvidenceContentProps) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [data, setData] = useState<EvidenceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [failureTypeFilter, setFailureTypeFilter] = useState("ALL");
  const [dateRangeFilter, setDateRangeFilter] = useState<DateRange>({ from: undefined, to: undefined });
  const [loading, setLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<EvidenceItem | null>(null);
  const [failureTypeStats, setFailureTypeStats] = useState<
    Array<{ type: string; label: string; count: number }>
  >([]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total]
  );

  const getPageItems = (current: number, totalCount: number): Array<number | string> => {
    if (totalCount <= 7) {
      return Array.from({ length: totalCount }, (_, idx) => idx + 1);
    }

    const items: Array<number | string> = [1];
    const start = Math.max(2, current - 1);
    const end = Math.min(totalCount - 1, current + 1);

    if (start > 2) items.push("...");
    for (let p = start; p <= end; p += 1) {
      items.push(p);
    }
    if (end < totalCount - 1) items.push("...");
    items.push(totalCount);

    return items;
  };

  const pageItems = useMemo(() => getPageItems(page, totalPages), [page, totalPages]);

  const fetchData = useCallback(
    async (params: { page: number; q: string; status: string; failureType: string; dateRange: DateRange }) => {
      setLoading(true);
      try {
        const searchParams = new URLSearchParams({
          page: String(params.page),
          page_size: String(PAGE_SIZE)
        });
        if (params.q) searchParams.set("q", params.q);
        if (params.status && params.status !== "ALL") searchParams.set("status", params.status);
        if (params.failureType && params.failureType !== "ALL") searchParams.set("failure_type", params.failureType);
        if (params.dateRange.from && params.dateRange.to) {
          searchParams.set("start_date", format(params.dateRange.from, "yyyy-MM-dd"));
          searchParams.set("end_date", format(params.dateRange.to, "yyyy-MM-dd"));
        }

        const res = await apiFetch(
          `/evidence/list?${searchParams.toString()}`
        );
        if (!res.ok) throw new Error("加载失败");
        const payload = await res.json();
        setData(payload.items || []);
        setTotal(payload.total || 0);
        setPage(payload.page || params.page);
        setPageInput(String(payload.page || params.page));
      } catch (error) {
        console.error("加载任务列表失败:", error);
        toast.error("加载任务列表失败");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const fetchFailureTypeStats = useCallback(async (dateRange?: DateRange) => {
    try {
      const params = new URLSearchParams();
      if (dateRange?.from && dateRange?.to) {
        params.set("start_date", format(dateRange.from, "yyyy-MM-dd"));
        params.set("end_date", format(dateRange.to, "yyyy-MM-dd"));
      }
      const dateRangeParam = params.toString() ? `?${params.toString()}` : "";
      const url = `/evidence/stats/failure-types${dateRangeParam}`;

      const res = await apiFetch(url);
      if (!res.ok) return;
      const payload = await res.json();
      setFailureTypeStats(payload.failure_type_distribution || []);
    } catch (error) {
      console.error('Failed to fetch failure type stats:', error);
    }
  }, []);

  useEffect(() => {
    // 从 URL 读取所有参数
    const urlPage = searchParams.get("page");
    const urlQuery = searchParams.get("q") || ""; // 默认空字符串
    let urlStatus = searchParams.get("status") || "ALL";
    let urlFailureType = searchParams.get("failure_type") || "ALL";
    // 读取时间范围参数
    const urlStartDate = searchParams.get("start_date");
    const urlEndDate = searchParams.get("end_date");

    // 将状态参数转换为大写，以匹配 statusOptions 中的值
    // 支持大小写不敏感的 URL 参数（如 ?status=failed 或 ?status=FAILED）
    if (urlStatus !== "ALL") {
      urlStatus = urlStatus.toUpperCase();
    }

    // 修正：只有 status=FAILED 时才保留 failure_type（与现有逻辑一致）
    if (urlStatus !== "FAILED") {
      urlFailureType = "ALL";
    }

    // 解析并验证 page（防止 NaN）
    let pageNum = 1;
    if (urlPage) {
      const parsed = parseInt(urlPage, 10);
      if (!isNaN(parsed) && parsed >= 1) {
        pageNum = parsed;
      }
    }

    // 将 URL 参数转换为 DateRange
    const dateRange: DateRange = urlStartDate && urlEndDate
      ? { from: new Date(urlStartDate), to: new Date(urlEndDate) }
      : { from: undefined, to: undefined };

    // 无条件更新所有状态（确保与 URL 完全同步）
    setPage(pageNum);
    setPageInput(String(pageNum));
    setQuery(urlQuery); // 即使是空字符串也设置
    setStatusFilter(urlStatus);
    setFailureTypeFilter(urlFailureType);
    setDateRangeFilter(dateRange);

    // 使用 URL 参数获取数据
    fetchData({
      page: pageNum,
      status: urlStatus,
      failureType: urlFailureType,
      q: urlQuery,
      dateRange: dateRange
    });

    // 获取失败类型统计，传递时间范围参数
    fetchFailureTypeStats(dateRange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchData({
        page,
        q: query,
        status: statusFilter,
        failureType: failureTypeFilter,
        dateRange: dateRangeFilter
      });
      // 定时刷新时也传递当前时间范围
      fetchFailureTypeStats(dateRangeFilter);
    }, 30_000);

    return () => clearInterval(interval);
  }, [fetchData, fetchFailureTypeStats, page, query, statusFilter, failureTypeFilter, dateRangeFilter]);

  const handleSearch = () => {
    const trimmedQuery = query.trim();
    setQuery(trimmedQuery);

    // 直接更新状态并获取数据
    setPage(1);
    setPageInput("1");
    fetchData({
      page: 1,
      q: trimmedQuery,
      status: statusFilter,
      failureType: failureTypeFilter,
      dateRange: dateRangeFilter
    });
  };

  const statusOptions: Array<{ value: string; label: string }> = [
    { value: "ALL", label: "全部" },
    { value: "SUCCESS", label: "成功" },
    { value: "FAILED", label: "失败" },
    { value: "RUNNING", label: "执行中" },
    { value: "PENDING", label: "待执行" }
  ];


  const failureTypeOptions: Array<{ value: string; label: string }> = useMemo(() => {
    const baseOptions = [
      { value: "ALL", label: "全部" }
    ];

    // 创建统计数据的映射表（来自后端API，匹配当前时间范围）
    const statsMap = new Map(
      failureTypeStats.map(stat => [stat.type, stat.count])
    );

    // 使用从 API 获取的失败类型列表（已按业务优先级排序）
    const optionsWithCount = failureTypes.map(option => {
      const count = statsMap.get(option.value);
      return {
        value: option.value,
        label: count !== undefined ? `${option.label}(${count})` : option.label
      };
    });

    return [...baseOptions, ...optionsWithCount];
  }, [failureTypeStats, failureTypes]);

  // 注意：时间范围选项现在由 DateRangePicker 组件统一管理

  const renderStatus = (value?: string) => {
    if (!value) return <span className="text-slate-400">-</span>;
    const label = STATUS_LABELS[value as TaskStatus] ?? value;

    const icon: Record<string, JSX.Element | null> = {
      PENDING: null,
      RUNNING: <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />,
      SUCCESS: null,
      FAILED: null
    };

    const pillClass = STATUS_STYLES[value as TaskStatus] || "bg-slate-100 text-slate-600 border border-slate-200";

    return (
      <span className={cn("inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium", pillClass)}>
        {icon[value]}
        {label}
      </span>
    );
  };

  const formatTaskDuration = (durationSeconds: number, status?: string) => {
    if (status === "PENDING" || status === "RUNNING") {
      return "-";
    }
    return formatDurationSeconds(durationSeconds);
  };

  const handlePageChange = (nextPage: number) => {
    // 直接更新状态并获取数据
    setPage(nextPage);
    setPageInput(String(nextPage));
    fetchData({
      page: nextPage,
      q: query,
      status: statusFilter,
      failureType: failureTypeFilter,
      dateRange: dateRangeFilter
    });
  };

  const handlePageJump = () => {
    const value = parseInt(pageInput, 10);
    if (Number.isNaN(value)) return;
    const target = Math.min(Math.max(1, value), totalPages);

    // 直接更新状态并获取数据
    setPage(target);
    setPageInput(String(target));
    fetchData({
      page: target,
      q: query,
      status: statusFilter,
      failureType: failureTypeFilter,
      dateRange: dateRangeFilter
    });
  };

  const handleStatusChange = (value: string) => {
    const newFailureType = value !== "FAILED" ? "ALL" : failureTypeFilter;

    // 如果切换到 PENDING 或 RUNNING，清空日期范围
    const newDateRange = (value === "PENDING" || value === "RUNNING")
      ? { from: undefined, to: undefined }
      : dateRangeFilter;

    // 更新状态
    setStatusFilter(value);
    if (value !== "FAILED") {
      setFailureTypeFilter("ALL");
    }
    if (value === "PENDING" || value === "RUNNING") {
      setDateRangeFilter({ from: undefined, to: undefined });
    }
    setPage(1);
    setPageInput("1");

    // 同步更新 URL 参数
    const params = new URLSearchParams(searchParams.toString());
    if (value && value !== "ALL") {
      params.set("status", value);
    } else {
      params.delete("status");
    }
    // 如果状态不是 FAILED，删除 failure_type 参数
    if (value !== "FAILED") {
      params.delete("failure_type");
    } else if (newFailureType !== "ALL") {
      params.set("failure_type", newFailureType);
    }
    // 如果状态是 PENDING 或 RUNNING，删除时间范围参数
    if (value === "PENDING" || value === "RUNNING") {
      params.delete("start_date");
      params.delete("end_date");
    } else if (newDateRange.from && newDateRange.to) {
      params.set("start_date", format(newDateRange.from, "yyyy-MM-dd"));
      params.set("end_date", format(newDateRange.to, "yyyy-MM-dd"));
    }
    // 保留查询参数
    if (query) {
      params.set("q", query);
    } else {
      params.delete("q");
    }
    router.push(`/evidence?${params.toString()}`);

    // 直接获取数据，使用新值
    fetchData({
      page: 1,
      q: query,
      status: value,
      failureType: newFailureType,
      dateRange: newDateRange
    });
  };

  const handleFailureTypeChange = (value: string) => {
    setFailureTypeFilter(value);
    setPage(1);
    setPageInput("1");

    // 同步更新 URL 参数
    const params = new URLSearchParams(searchParams.toString());
    if (value && value !== "ALL") {
      params.set("failure_type", value);
    } else {
      params.delete("failure_type");
    }
    // 保留其他筛选参数
    if (statusFilter && statusFilter !== "ALL") {
      params.set("status", statusFilter);
    }
    if (dateRangeFilter.from && dateRangeFilter.to) {
      params.set("start_date", format(dateRangeFilter.from, "yyyy-MM-dd"));
      params.set("end_date", format(dateRangeFilter.to, "yyyy-MM-dd"));
    }
    if (query) {
      params.set("q", query);
    } else {
      params.delete("q");
    }
    router.push(`/evidence?${params.toString()}`);

    // 直接获取数据，使用新值
    fetchData({
      page: 1,
      q: query,
      status: statusFilter,
      failureType: value,
      dateRange: dateRangeFilter
    });
  };

  const handleDateRangeChange = (value: DateRange) => {
    setDateRangeFilter(value);
    setPage(1);
    setPageInput("1");

    // 同步更新 URL 参数，保留当前的 status 和其他筛选参数
    const params = new URLSearchParams(searchParams.toString());
    if (value.from && value.to) {
      params.set("start_date", format(value.from, "yyyy-MM-dd"));
      params.set("end_date", format(value.to, "yyyy-MM-dd"));
    } else {
      // 如果选择"全部"，移除时间范围参数
      params.delete("start_date");
      params.delete("end_date");
    }
    // 从组件状态读取 status，确保保留当前筛选
    if (statusFilter && statusFilter !== "ALL") {
      params.set("status", statusFilter);
    }
    // 保留 failure_type（如果存在）
    if (statusFilter === "FAILED" && failureTypeFilter && failureTypeFilter !== "ALL") {
      params.set("failure_type", failureTypeFilter);
    }
    // 保留查询参数
    if (query) {
      params.set("q", query);
    } else {
      params.delete("q");
    }
    router.push(`/evidence?${params.toString()}`);

    // 直接获取数据，使用新值
    fetchData({
      page: 1,
      q: query,
      status: statusFilter,
      failureType: failureTypeFilter,
      dateRange: value
    });
    // 更新失败类型统计（带时间范围参数）
    fetchFailureTypeStats(value);
  };

  const handleRowClick = (item: EvidenceItem) => {
    setSelectedItem(item);
  };

  const handleCloseModal = () => {
    setSelectedItem(null);
  };

  return (
    <div className="flex h-full flex-col">
      {/* 顶部操作栏 */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-700">状态</span>
            <Select
              value={statusFilter}
              onValueChange={handleStatusChange}
              disabled={loading}
            >
              <SelectTrigger className="w-[120px] h-10 border-slate-200 bg-white shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
                <SelectValue placeholder="全部" />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((option) => (
                  <SelectItem key={option.value || "all"} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {statusFilter === "FAILED" && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">失败类型</span>
              <Select
                value={failureTypeFilter}
                onValueChange={handleFailureTypeChange}
                disabled={loading}
              >
                <SelectTrigger className="w-[180px] h-10 border-slate-200 bg-white shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  {failureTypeOptions.map((option) => (
                    <SelectItem key={option.value || "all"} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {/* 只在 SUCCESS 或 FAILED 状态时显示时间范围选择框 */}
          {(statusFilter === "ALL" || statusFilter === "SUCCESS" || statusFilter === "FAILED") && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">时间范围</span>
              <DateRangePicker
                value={dateRangeFilter}
                onChange={handleDateRangeChange}
                className="min-w-[200px] h-10 border-slate-200 bg-white shadow-[0_6px_18px_rgba(15,23,42,0.06)]"
              />
            </div>
          )}
        </div>
        <div className="relative flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
          <Search className="pointer-events-none absolute left-4 h-4 w-4 text-slate-400" />
          <Input
            placeholder="按 URL 搜索"
            className="h-10 w-56 border-0 bg-transparent pl-9 pr-24 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSearch();
              }
            }}
          />
          <Button
            size="sm"
            className="ml-2 h-9 rounded-lg px-4 bg-sky-500 text-white shadow-sm hover:bg-sky-500/90 disabled:opacity-70"
            onClick={handleSearch}
            disabled={loading}
          >
            搜索
          </Button>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 overflow-y-auto">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="grid grid-cols-[70px_1.4fr_0.8fr_1.1fr_0.8fr_2fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>ID</div>
          <div>网址</div>
          <div>任务状态</div>
          <div>任务执行时间</div>
          <div>任务时长</div>
          <div>任务结果</div>
        </div>
        <div className="divide-y divide-slate-100">
          {loading ? (
            <div className="flex items-center justify-center gap-2 px-4 py-6 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载...
            </div>
          ) : data.length === 0 ? (
            <div className="px-4 py-6 text-sm text-slate-500">暂无数据</div>
          ) : (
            data.map((item, idx) => (
              <div
                key={`${item.id}-${idx}`}
                className={cn(
                  "grid grid-cols-[70px_1.4fr_0.8fr_1.1fr_0.8fr_2fr] items-center px-4 py-3 text-sm text-slate-700",
                  idx % 2 === 0 ? "bg-white" : "bg-slate-50/70",
                  "cursor-pointer transition-colors hover:bg-slate-100/80"
                )}
                onClick={() => handleRowClick(item)}
              >
                <div className="font-mono text-xs text-slate-500">
                  {item.id ?? (page - 1) * PAGE_SIZE + idx + 1}
                </div>
                <div className="truncate pr-4" title={item.url}>
                  {item.url}
                </div>
                <div className="truncate pr-4 text-slate-600">
                  {renderStatus(item.status)}
                </div>
                <div className="truncate pr-4" title={item.executed_at || undefined}>
                  {formatDateTime(item.executed_at)}
                </div>
                <div className="truncate pr-4">{formatTaskDuration(item.duration_seconds, item.status)}</div>
                <div className="flex items-center gap-2 min-w-0" title={item.result || undefined}>
                  {item.status === "FAILED" && item.failure_type && (
                    <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10 flex-shrink-0">
                      {failureTypeLabel[item.failure_type] || item.failure_type}
                    </span>
                  )}
                  <span className="truncate">
                    {item.result || "-"}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
        <div>
          共 {total} 条 · 第 {page}/{totalPages} 页
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(Math.max(1, page - 1))}
              disabled={page === 1 || loading}
            >
              {"<"}
            </Button>
            {pageItems.map((item, idx) =>
              typeof item === "string" ? (
                <span key={`ellipsis-${idx}`} className="px-2 text-slate-400">
                  {item}
                </span>
              ) : (
                <Button
                  key={item}
                  variant={item === page ? "default" : "outline"}
                  size="sm"
                  className={cn(
                    "min-w-9",
                    item === page
                      ? "bg-emerald-500 text-white shadow hover:bg-emerald-500"
                      : "bg-white text-slate-700"
                  )}
                  onClick={() => handlePageChange(item)}
                  disabled={loading}
                >
                  {item}
                </Button>
              )
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
              disabled={page === totalPages || loading}
            >
              {">"}
            </Button>
          </div>
          <div className="flex items-center gap-1">
            <Input
              type="number"
              min={1}
              max={totalPages}
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              className="h-9 w-20"
            />
            <Button variant="outline" size="sm" onClick={handlePageJump} disabled={loading}>
              跳转
            </Button>
          </div>
        </div>
      </div>

      {selectedItem && (
        <TaskDetailModal
          task={selectedItem}
          onClose={handleCloseModal}
          failureTypeLabel={failureTypeLabel}
        />
      )}
      </div>
    </div>
  );
}

// Export the main component wrapped in Suspense
type TaskListDrawerProps = {
  failureTypes: FailureTypeItem[];
  failureTypeLabel: Record<string, string>;
};

export function TaskListDrawer({ failureTypes, failureTypeLabel }: TaskListDrawerProps) {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center gap-2 px-4 py-12 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载中...
      </div>
    }>
      <EvidenceContent failureTypes={failureTypes} failureTypeLabel={failureTypeLabel} />
    </Suspense>
  );
}
