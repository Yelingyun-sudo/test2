"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { cn } from "@/lib/utils";

type UnsubscribedItem = { id: number; url: string; created_at: string };
type UnsubscribedListResponse = {
  items: UnsubscribedItem[];
  total: number;
  page: number;
  page_size: number;
};

const PAGE_SIZE = 15;

export default function UnsubscribedPage() {
  const [data, setData] = useState<UnsubscribedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

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
    async (params?: { page?: number; q?: string }) => {
      const currentPage = params?.page ?? page;
      const q = params?.q ?? query;
      setLoading(true);
      try {
        const searchParams = new URLSearchParams({
          page: String(currentPage),
          page_size: String(PAGE_SIZE)
        });
        if (q) searchParams.set("q", q);

        const res = await apiFetch(
          `/evidence/list?${searchParams.toString()}`
        );
        if (!res.ok) throw new Error("加载失败");
        const payload = (await res.json()) as UnsubscribedListResponse;
        setData(payload.items);
        setTotal(payload.total);
        setPage(payload.page);
        setPageInput(String(payload.page));
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    },
    [page, query]
  );

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchData();
    }, 30_000);

    return () => clearInterval(interval);
  }, [fetchData]);

  const handleSearch = () => {
    fetchData({ page: 1, q: query.trim() });
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
      title="注册取证任务"
      description="管理注册取证任务，支持按 URL 检索。"
      actions={
        <div className="flex items-center gap-2">
          <div className="relative flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
            <Search className="pointer-events-none absolute left-4 h-4 w-4 text-slate-400" />
            <Input
              placeholder="按 URL 搜索"
              className="h-10 w-64 border-0 bg-transparent pl-9 pr-24 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSearch();
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
        <div className="grid grid-cols-[70px_1.4fr_1.1fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>ID</div>
          <div>网址</div>
          <div>任务创建时间</div>
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
                  "grid grid-cols-[70px_1.4fr_1.1fr] items-center px-4 py-3 text-sm text-slate-700",
                  idx % 2 === 0 ? "bg-white" : "bg-slate-50/70",
                  "transition-colors hover:bg-slate-100/80"
                )}
              >
                <div className="font-mono text-xs text-slate-500">
                  {item.id ?? (page - 1) * PAGE_SIZE + idx + 1}
                </div>
                <div className="truncate pr-4" title={item.url}>
                  {item.url}
                </div>
                <div className="truncate" title={item.created_at || undefined}>
                  {formatDateTime(item.created_at)}
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
    </DashboardShell>
  );
}
