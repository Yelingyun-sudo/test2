"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type SubscribedItem = {
  id: number;
  url: string;
  account: string;
  password: string;
  status: string;
  duration_seconds: number;
  retry_count: number;
  history_extract_count: number;
  last_extracted_at?: string | null;
  result?: string | null;
};

type SubscribedListResponse = {
  items: SubscribedItem[];
  total: number;
  page: number;
  page_size: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

const PAGE_SIZE = 15;

export default function SubscribedPage() {
  const [data, setData] = useState<SubscribedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<SubscribedItem | null>(null);

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

  const fetchData = async (params?: { page?: number; q?: string; status?: string }) => {
    const currentPage = params?.page ?? page;
    const q = params?.q ?? query;
    const status = params?.status ?? statusFilter;
    setLoading(true);
    try {
      const searchParams = new URLSearchParams({
        page: String(currentPage),
        page_size: String(PAGE_SIZE)
      });
      if (q) searchParams.set("q", q);
      if (status) searchParams.set("status", status);

      const res = await fetch(
        `${API_BASE_URL}/subscribed/list?${searchParams.toString()}`
      );
      if (!res.ok) throw new Error("加载失败");
      const payload = (await res.json()) as SubscribedListResponse;
      setData(payload.items);
      setTotal(payload.total);
      setPage(payload.page);
      setPageInput(String(payload.page));
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = () => {
    fetchData({ page: 1, q: query.trim(), status: statusFilter });
  };

  const statusLabel: Record<string, string> = {
    pending: "待执行",
    running: "执行中",
    success: "成功",
    failed: "失败"
  };

  const statusOptions: Array<{ value: string; label: string }> = [
    { value: "", label: "全部" },
    ...Object.entries(statusLabel).map(([value, label]) => ({ value, label }))
  ];

  const renderStatus = (value?: string) => {
    if (!value) return <span className="text-slate-400">-</span>;
    const key = value.toLowerCase();
    const label = statusLabel[key] ?? value;

    const styles: Record<string, string> = {
      pending: "bg-slate-100 text-slate-600 border border-slate-200",
      running: "bg-emerald-50 text-emerald-600 border border-emerald-100",
      success: "bg-emerald-50 text-emerald-600 border border-emerald-100",
      failed: "bg-rose-50 text-rose-600 border border-rose-100"
    };

    const icon: Record<string, JSX.Element | null> = {
      pending: null,
      running: <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />,
      success: null,
      failed: null
    };

    const pillClass = styles[key] || "bg-slate-100 text-slate-600 border border-slate-200";

    return (
      <span className={cn("inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium", pillClass)}>
        {icon[key]}
        {label}
      </span>
    );
  };

  const formatDateTime = (value?: string | null) => {
    if (!value) return "-";
    const normalized = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)
      ? `${value}Z`
      : value;

    const d = new Date(normalized);
    if (Number.isNaN(d.getTime())) return value;

    const formatter = new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    });

    const parts = formatter.formatToParts(d);
    const pick = (type: string) => parts.find((p) => p.type === type)?.value ?? "";

    return `${pick("year")}-${pick("month")}-${pick("day")} ${pick("hour")}:${pick("minute")}:${pick("second")}`;
  };

  const handlePageChange = (nextPage: number) => {
    fetchData({ page: nextPage });
  };

  const handlePageJump = () => {
    const value = parseInt(pageInput, 10);
    if (Number.isNaN(value)) return;
    const target = Math.min(Math.max(1, value), totalPages);
    fetchData({ page: target });
  };

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    fetchData({ page: 1, status: value, q: query.trim() });
  };

  const handleRowClick = (item: SubscribedItem) => {
    setSelectedItem(item);
  };

  const handleCloseModal = () => setSelectedItem(null);

  return (
    <DashboardShell
      title="已订阅网站"
      actions={
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
            <span className="text-sm font-semibold text-slate-700">状态</span>
            <select
              value={statusFilter}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="h-9 min-w-[120px] rounded-md bg-transparent text-sm text-slate-800 focus:outline-none"
              disabled={loading}
              aria-label="状态筛选"
            >
              {statusOptions.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="relative flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
            <Search className="pointer-events-none absolute left-4 h-4 w-4 text-slate-400" />
            <Input
              placeholder="按 URL 搜索"
              className="h-10 w-64 border-0 bg-transparent pl-9 pr-24 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
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
      }
    >
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="grid grid-cols-[70px_1.4fr_0.65fr_0.6fr_0.6fr_0.6fr_1.1fr_2fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>ID</div>
          <div>网址</div>
          <div>任务状态</div>
          <div>任务时长</div>
          <div>重试次数</div>
          <div>历史提取次数</div>
          <div>最后一次提取时间</div>
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
                  "grid grid-cols-[70px_1.4fr_0.65fr_0.6fr_0.6fr_0.6fr_1.1fr_2fr] items-center px-4 py-3 text-sm text-slate-700",
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
                <div className="truncate pr-4 text-slate-600 flex items-center">
                  {renderStatus(item.status)}
                </div>
                <div className="truncate pr-4">{item.duration_seconds}</div>
                <div className="truncate pr-4">{item.retry_count}</div>
                <div className="truncate pr-4">{item.history_extract_count}</div>
                <div className="truncate pr-4" title={item.last_extracted_at || undefined}>
                  {formatDateTime(item.last_extracted_at)}
                </div>
                <div className="truncate" title={item.result || undefined}>
                  {item.result || "-"}
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
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={handleCloseModal}
        >
          <div
            className="relative w-full max-w-4xl rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="订阅任务详情"
          >
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-slate-900">订阅任务详情</h3>
                <p className="text-sm text-slate-500">ID: {selectedItem.id ?? "-"}</p>
              </div>
              <Button variant="outline" size="sm" onClick={handleCloseModal}>
                关闭
              </Button>
            </div>

            <div className="grid gap-4 px-6 py-5 text-sm text-slate-700 sm:grid-cols-2">
              <div className="space-y-1">
                <div className="text-slate-500">网址</div>
                <div className="break-all font-medium text-slate-800">{selectedItem.url}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">用户名</div>
                <div className="break-all font-medium text-slate-800">{selectedItem.account}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务状态</div>
                <div className="flex items-center gap-2">{renderStatus(selectedItem.status)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">密码</div>
                <div className="break-all font-medium text-slate-800">{selectedItem.password}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务时长 (s)</div>
                <div className="font-medium">{selectedItem.duration_seconds}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">重试次数</div>
                <div className="font-medium">{selectedItem.retry_count}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">历史提取次数</div>
                <div className="font-medium">{selectedItem.history_extract_count}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">最后一次提取时间</div>
                <div className="font-medium">{formatDateTime(selectedItem.last_extracted_at)}</div>
              </div>
            </div>

            <div className="px-6 pb-6">
              <div className="mb-2 text-sm font-semibold text-slate-700">任务结果</div>
              <textarea
                readOnly
                value={selectedItem.result ?? ""}
                placeholder="暂无结果"
                className="h-64 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm leading-relaxed text-slate-800 shadow-inner focus:outline-none"
              />
            </div>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
