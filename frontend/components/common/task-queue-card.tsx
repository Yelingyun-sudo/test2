"use client";

import { ChevronRight, Loader2 } from "lucide-react";

type TaskQueueCardLayout = "vertical" | "horizontal";

type TaskQueueCardProps = {
  pendingCount: number;
  runningCount: number;
  onClick?: () => void;
  onStatusClick?: (status: "running" | "pending") => void;
  layout?: TaskQueueCardLayout; // 默认 vertical
};

export function TaskQueueCard({
  pendingCount,
  runningCount,
  onClick,
  onStatusClick,
  layout = "vertical"
}: TaskQueueCardProps) {
  const handleStatusClick = (status: "running" | "pending", e: React.MouseEvent) => {
    e.stopPropagation();
    if (onStatusClick) {
      onStatusClick(status);
    } else if (onClick) {
      onClick();
    }
  };

  // 垂直布局（默认）
  if (layout === "vertical") {
    return (
      <div className="rounded-2xl border bg-gradient-to-br from-amber-500/10 to-amber-600/10 text-amber-700 border-amber-100 p-5 shadow-sm backdrop-blur">
        <div className="space-y-2">
          {/* 执行中区域 */}
          <div
            onClick={(e) => handleStatusClick("running", e)}
            className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/40 hover:bg-white/60 cursor-pointer transition-all hover:scale-[1.02] group"
          >
            <div className="flex items-center gap-2.5">
              {runningCount > 0 ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full bg-amber-400/60" />
              )}
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-semibold text-amber-700">{runningCount}</span>
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
                <span className="text-xl font-semibold text-slate-700">{pendingCount}</span>
                <span className="text-xs text-slate-600">待执行</span>
              </div>
            </div>
            <ChevronRight className="h-3.5 w-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </div>
    );
  }

  // 横向布局
  return (
    <div className="rounded-xl border bg-gradient-to-br from-amber-500/10 to-amber-600/10 border-amber-100 px-4 py-2.5 shadow-sm backdrop-blur">
      <div className="flex items-center gap-3">
        {/* 执行中 */}
        <div
          onClick={(e) => handleStatusClick("running", e)}
          className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/40 hover:bg-white/60 cursor-pointer transition-colors group"
        >
          {runningCount > 0 ? (
            <Loader2 className="h-3 w-3 animate-spin text-amber-600" />
          ) : (
            <span className="h-3 w-3 rounded-full bg-amber-400/60" />
          )}
          <div className="flex items-baseline gap-1">
            <span className="text-base font-semibold text-amber-700">{runningCount}</span>
            <span className="text-xs text-slate-600">执行中</span>
          </div>
          <ChevronRight className="h-3 w-3 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        {/* 分隔符 */}
        <div className="h-6 w-px bg-slate-200" />

        {/* 待执行 */}
        <div
          onClick={(e) => handleStatusClick("pending", e)}
          className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/40 hover:bg-white/60 cursor-pointer transition-colors group"
        >
          <span className="h-3 w-3 rounded-full bg-slate-400/60" />
          <div className="flex items-baseline gap-1">
            <span className="text-base font-semibold text-slate-700">{pendingCount}</span>
            <span className="text-xs text-slate-600">待执行</span>
          </div>
          <ChevronRight className="h-3 w-3 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </div>
  );
}
