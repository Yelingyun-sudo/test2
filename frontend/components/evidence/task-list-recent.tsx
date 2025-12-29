"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDateTime, formatDurationSeconds } from "@/lib/datetime";
import { cn } from "@/lib/utils";
import type { EvidenceItem } from "@/types/evidence";
import { STATUS_LABELS, STATUS_STYLES, type TaskStatus } from "@/types/common";

type TaskListRecentProps = {
  tasks: EvidenceItem[];
  total: number;
  failureTypeLabel: Record<string, string>;
  onTaskClick: (task: EvidenceItem) => void;
  onViewAll: () => void;
};

export function TaskListRecent({
  tasks,
  total,
  failureTypeLabel,
  onTaskClick,
  onViewAll,
}: TaskListRecentProps) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm h-[350px] flex flex-col">
      <div className="flex items-start justify-between">
        <h3 className="text-lg font-semibold text-slate-900">最新任务列表</h3>
        <Button
          variant="outline"
          size="sm"
          onClick={onViewAll}
          className="group border-sky-200 text-sky-600 hover:bg-sky-200 hover:border-sky-300 hover:text-sky-800 transition-colors duration-200"
        >
          显示全部
          <ArrowRight className="ml-1 h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
        </Button>
      </div>
      <div className="mt-4 flex-1 overflow-y-auto overflow-x-auto scrollbar-hover">
        <table className="w-full border-collapse">
          <colgroup>
            <col className="w-[5%]" />
            <col className="w-[14%]" />
            <col className="w-[12%]" />
            <col className="w-[23%]" />
            <col className="w-[12%]" />
            <col className="w-[34%]" />
          </colgroup>
          <thead>
            <tr className="border-b border-slate-200">
              <th className="p-2 text-left text-xs font-medium text-slate-500">ID</th>
              <th className="p-2 text-left text-xs font-medium text-slate-500">网址</th>
              <th className="p-2 text-left text-xs font-medium text-slate-500">状态</th>
              <th className="p-2 text-left text-xs font-medium text-slate-500">执行时间</th>
              <th className="p-2 text-left text-xs font-medium text-slate-500">耗时</th>
              <th className="p-2 text-left text-xs font-medium text-slate-500">结果</th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-4 text-center text-sm text-slate-500">
                  暂无任务记录
                </td>
              </tr>
            ) : (
              tasks.map((task) => (
                <tr
                  key={task.id}
                  className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => onTaskClick(task)}
                >
                  <td className="p-2 text-sm text-slate-700">{task.id}</td>
                  <td className="p-2 text-sm text-slate-700">
                    <div className="max-w-[160px] truncate" title={task.url}>
                      {task.url}
                    </div>
                  </td>
                  <td className="p-2">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
                        STATUS_STYLES[task.status as TaskStatus] ||
                          "bg-slate-100 text-slate-600 border border-slate-200"
                      )}
                    >
                      {task.status === "RUNNING" && (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      )}
                      {STATUS_LABELS[task.status as TaskStatus] || task.status}
                    </span>
                  </td>
                  <td className="p-2 text-sm text-slate-700">
                    {task.executed_at ? formatDateTime(task.executed_at) : "-"}
                  </td>
                  <td className="p-2 text-sm text-slate-700">
                    {task.status === "RUNNING" || task.status === "PENDING"
                      ? "-"
                      : formatDurationSeconds(task.duration_seconds)}
                  </td>
                  <td className="p-2 text-sm text-slate-700">
                    <div className="flex items-center gap-2 min-w-0 max-w-[270px]">
                      {task.status === "FAILED" && task.failure_type && (
                        <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10 flex-shrink-0">
                          {failureTypeLabel[task.failure_type] || task.failure_type}
                        </span>
                      )}
                      <span className="truncate" title={task.result || ""}>
                        {task.result || "-"}
                      </span>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
