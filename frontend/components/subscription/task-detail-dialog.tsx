"use client";

import { formatDateTime } from "@/lib/datetime";
import { cn } from "@/lib/utils";

// 类型定义
type LLMUsage = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  llm_turns: number;
  total_cached_tokens?: number;
  total_reasoning_tokens?: number;
};

export type TaskItem = {
  id: number;
  url: string;
  account?: string;
  password?: string;
  status: string;
  created_at?: string | null;
  duration_seconds: number | null;
  executed_at?: string | null;
  task_dir?: string | null;
  result?: string | null;
  failure_type?: string | null;
  llm_usage?: LLMUsage | null;
};

type TaskDetailDialogProps = {
  task: TaskItem | null;
  onClose: () => void;
};

// 辅助函数
function formatNumber(num: number | undefined): string {
  if (num === undefined || num === null) return "0";
  return num.toLocaleString("zh-CN");
}

function formatDurationSeconds(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const totalSeconds = Math.max(0, Math.floor(value));
  if (totalSeconds < 60) return `${totalSeconds}秒`;

  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (totalSeconds < 3600) return `${minutes}分${seconds}秒`;
  if (totalSeconds < 86_400) return `${hours}小时${minutes}分${seconds}秒`;
  return `${days}天${hours}小时${minutes}分${seconds}秒`;
}

const statusLabel: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  success: "成功",
  failed: "失败"
};

const statusStyles: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  running: "bg-yellow-100 text-yellow-700",
  success: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700"
};

export function TaskDetailDialog({ task, onClose }: TaskDetailDialogProps) {
  if (!task) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        className="relative w-full max-w-4xl rounded-2xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 z-10">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">任务详情</h3>
              <p className="text-sm text-slate-500">ID: {task.id}</p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
            >
              关闭
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-6">
          {/* 基本信息 */}
          <div className="grid gap-4 text-sm sm:grid-cols-2">
            <div className="space-y-1">
              <div className="text-slate-500">网址</div>
              <div className="break-all font-medium text-slate-800">{task.url}</div>
            </div>
            
            {task.account && (
              <div className="space-y-1">
                <div className="text-slate-500">账号</div>
                <div className="break-all font-medium text-slate-800">{task.account}</div>
              </div>
            )}
            
            <div className="space-y-1">
              <div className="text-slate-500">任务状态</div>
              <div>
                <span
                  className={cn(
                    "inline-block rounded-full px-3 py-1 text-xs font-medium",
                    statusStyles[task.status] || "bg-slate-100 text-slate-700"
                  )}
                >
                  {statusLabel[task.status] || task.status}
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-slate-500">任务创建时间</div>
              <div className="font-medium text-slate-700">
                {formatDateTime(task.created_at)}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-slate-500">任务执行时间</div>
              <div className="font-medium text-slate-700">
                {formatDateTime(task.executed_at)}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-slate-500">任务时长</div>
              <div className="font-medium text-slate-700">
                {task.status === "running" || task.status === "pending"
                  ? "-"
                  : formatDurationSeconds(task.duration_seconds)}
              </div>
            </div>
          </div>

          {/* LLM 使用情况 */}
          {task.llm_usage && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <h4 className="text-sm font-semibold text-slate-900 mb-3">Token 使用情况</h4>
              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <div className="text-slate-500">输入 Token</div>
                  <div className="font-mono text-blue-600 font-medium">
                    {formatNumber(task.llm_usage.total_input_tokens)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">输出 Token</div>
                  <div className="font-mono text-green-600 font-medium">
                    {formatNumber(task.llm_usage.total_output_tokens)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">总计 Token</div>
                  <div className="font-mono text-slate-900 font-bold">
                    {formatNumber(task.llm_usage.total_tokens)}
                  </div>
                </div>
              </div>
              {task.llm_usage.llm_turns > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-200">
                  <div className="text-slate-500 text-xs">LLM 轮次</div>
                  <div className="font-medium text-slate-700">{task.llm_usage.llm_turns}</div>
                </div>
              )}
            </div>
          )}

          {/* 任务结果 */}
          {task.result && (
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-900">任务结果</div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm text-slate-700 break-all">{task.result}</div>
              </div>
            </div>
          )}

          {/* 失败类型 */}
          {task.failure_type && (
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-900">失败类型</div>
              <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                <div className="text-sm text-red-700">{task.failure_type}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

