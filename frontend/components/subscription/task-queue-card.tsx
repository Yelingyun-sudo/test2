"use client";

import { useEffect, useState, useMemo } from "react";
import { Loader2, ChevronRight } from "lucide-react";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api";
import type { SubscriptionListResponse } from "@/types/subscription";

type TaskQueueCardProps = {
  onClick?: () => void;
  onStatusClick?: (status: "running" | "pending") => void;
};

export function TaskQueueCard({ onClick, onStatusClick }: TaskQueueCardProps) {
  const [tasks, setTasks] = useState<Array<{ status: string }>>([]);
  const [loading, setLoading] = useState(false);

  // 按状态分组任务
  const groupedTasks = useMemo(() => {
    const running = tasks.filter((task) => task.status === "RUNNING");
    const pending = tasks.filter((task) => task.status === "PENDING");
    return { running, pending };
  }, [tasks]);

  // 初始加载和自动刷新
  useEffect(() => {
    // 获取任务列表
    const fetchTasks = async () => {
      try {
        setLoading(true);
        // FastAPI支持多个同名参数，手动构建URL字符串
        const url = `/subscription/list?status=pending&status=running&page=1&page_size=100`;
        
        const res = await apiFetch(url);
        if (!res.ok) {
          throw new Error("获取任务列表失败");
        }
        const data = (await res.json()) as SubscriptionListResponse;
        setTasks(data.items || []);
      } catch (error) {
        console.error("获取任务列表失败", error);
        toast.error("获取任务列表失败");
      } finally {
        setLoading(false);
      }
    };

    // 立即加载一次
    fetchTasks();

    // 每5秒刷新一次
    const interval = setInterval(() => {
      fetchTasks();
    }, 5000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  const totalRunning = groupedTasks.running.length;
  const totalPending = groupedTasks.pending.length;

  const handleStatusClick = (status: "running" | "pending", e: React.MouseEvent) => {
    e.stopPropagation();
    if (onStatusClick) {
      onStatusClick(status);
    } else if (onClick) {
      onClick();
    }
  };

  return (
    <div className="rounded-2xl border bg-gradient-to-br from-amber-500/10 to-amber-600/10 text-amber-700 border-amber-100 p-5 shadow-sm backdrop-blur">
      {loading && tasks.length === 0 ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-amber-600" />
          <span className="ml-2 text-sm text-slate-600">加载中...</span>
        </div>
      ) : (
        <div className="space-y-2">
          {/* 执行中区域 */}
          <div
            onClick={(e) => handleStatusClick("running", e)}
            className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/40 hover:bg-white/60 cursor-pointer transition-all hover:scale-[1.02] group"
          >
            <div className="flex items-center gap-2.5">
              {totalRunning > 0 ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full bg-amber-400/60" />
              )}
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-semibold text-amber-700">{totalRunning}</span>
                <span className="text-xs text-slate-600">执行中</span>
              </div>
            </div>
            <ChevronRight className="h-3.5 w-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>

          {/* 待执行区域 */}
          <div
            onClick={(e) => handleStatusClick("pending", e)}
            className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/40 hover:bg-white/60 cursor-pointer transition-all hover:scale-[1.02] group"
          >
            <div className="flex items-center gap-2.5">
              <span className="h-3.5 w-3.5 rounded-full bg-slate-400/60" />
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-semibold text-slate-700">{totalPending}</span>
                <span className="text-xs text-slate-600">待执行</span>
              </div>
            </div>
            <ChevronRight className="h-3.5 w-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      )}
    </div>
  );
}


