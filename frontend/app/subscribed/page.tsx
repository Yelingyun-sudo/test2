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
  const [loading, setLoading] = useState(false);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total]
  );

  const fetchData = async (params?: { page?: number; q?: string }) => {
    const currentPage = params?.page ?? page;
    const q = params?.q ?? query;
    setLoading(true);
    try {
      const searchParams = new URLSearchParams({
        page: String(currentPage),
        page_size: String(PAGE_SIZE)
      });
      if (q) searchParams.set("q", q);

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
    fetchData({ page: 1, q: query.trim() });
  };

  const statusLabel: Record<string, string> = {
    pending: "待执行",
    running: "执行中",
    success: "成功",
    failed: "失败"
  };

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
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
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

  return (
    <DashboardShell
      title="已订阅网站"
      description="读取数据库订阅任务，支持分页与简单检索。"
      actions={
        <div className="flex items-center gap-2">
          <div className="relative flex items-center">
            <Search className="pointer-events-none absolute left-3 h-4 w-4 text-slate-400" />
            <Input
              placeholder="按 URL 搜索"
              className="pl-9 pr-24"
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
              className="absolute right-1 h-8 px-3"
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
        <div className="grid grid-cols-[80px_2fr_1fr_1fr_1fr_1fr_1.4fr_1.5fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>ID</div>
          <div>网址</div>
          <div>任务状态</div>
          <div>任务时长(s)</div>
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
                  "grid grid-cols-[80px_2fr_1fr_1fr_1fr_1fr_1.4fr_1.5fr] items-center px-4 py-3 text-sm text-slate-700",
                  idx % 2 === 0 ? "bg-white" : "bg-slate-50/70"
                )}
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
        <div className="flex items-center gap-2">
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
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(Math.max(1, page - 1))}
            disabled={page === 1 || loading}
          >
            上一页
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
            disabled={page === totalPages || loading}
          >
            下一页
          </Button>
        </div>
      </div>
    </DashboardShell>
  );
}
