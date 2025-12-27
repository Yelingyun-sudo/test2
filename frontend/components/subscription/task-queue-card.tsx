"use client";

import { ChevronRight, Loader2 } from "lucide-react";

type TaskQueueCardProps = {
  pendingCount: number;
  runningCount: number;
  onClick?: () => void;
  onStatusClick?: (status: "running" | "pending") => void;
};

export function TaskQueueCard({ 
  pendingCount, 
  runningCount, 
  onClick, 
  onStatusClick 
}: TaskQueueCardProps) {
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


