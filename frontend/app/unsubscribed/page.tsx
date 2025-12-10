"use client";

import { useEffect, useMemo, useState } from "react";
import { CircleOff, Loader2, Search } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type UnsubscribedItem = { url: string };
type UnsubscribedListResponse = {
  items: UnsubscribedItem[];
  total: number;
  page: number;
  page_size: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
const PAGE_SIZE = 20;

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
        `${API_BASE_URL}/unsubscribed/list?${searchParams.toString()}`
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
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      title="未订阅网站"
      description="读取后端未订阅数据文件，支持分页与检索。"
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
                if (e.key === "Enter") handleSearch();
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
        <div className="grid grid-cols-[80px_1fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>序号</div>
          <div>未订阅 URL</div>
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
                key={`${item.url}-${idx}`}
                className={cn(
                  "grid grid-cols-[80px_1fr] items-center px-4 py-3 text-sm text-slate-700",
                  idx % 2 === 0 ? "bg-white" : "bg-slate-50/70"
                )}
              >
                <div className="font-mono text-xs text-slate-500">
                  {(page - 1) * PAGE_SIZE + idx + 1}
                </div>
                <div className="truncate pr-4">{item.url}</div>
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
