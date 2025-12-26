"use client";

import { useEffect, useState, useMemo } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { cn } from "@/lib/utils";
import type { SubscriptionItem, SubscriptionListResponse } from "@/types/subscription";
import { STATUS_LABELS, STATUS_STYLES, type TaskStatus } from "@/types/common";
import { TaskDetailModal } from "./task-detail-modal";

type TaskQueueModalProps = {
  open: boolean;
  onClose: () => void;
};

export function TaskQueueModal({ open, onClose }: TaskQueueModalProps) {
  const [tasks, setTasks] = useState<SubscriptionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<SubscriptionItem | null>(null);

  // 按状态分组任务
  const groupedTasks = useMemo(() => {
    const running = tasks.filter((task) => task.status === "RUNNING");
    const pending = tasks.filter((task) => task.status === "PENDING");
    return { running, pending };
  }, [tasks]);

  // 初始加载和自动刷新
  useEffect(() => {
    if (!open) {
      // 关闭时清除任务列表
      setTasks([]);
      return;
    }

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
  }, [open]);

  if (!open) return null;

  const totalRunning = groupedTasks.running.length;
  const totalPending = groupedTasks.pending.length;

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        onClick={onClose}
      >
        <div
          className="relative w-full max-w-4xl rounded-2xl bg-white shadow-2xl"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label="任务队列"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <div className="space-y-1">
              <h3 className="text-lg font-semibold text-slate-900">任务队列</h3>
              <p className="text-sm text-slate-500">
                执行中 {totalRunning} 个 · 待执行 {totalPending} 个
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={onClose}>
              关闭
            </Button>
          </div>

          {/* Content */}
          <div className="max-h-[500px] overflow-y-auto px-6 py-4">
            {loading && tasks.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                <span className="ml-2 text-sm text-slate-500">加载中...</span>
              </div>
            ) : totalRunning === 0 && totalPending === 0 ? (
              <div className="py-12 text-center text-sm text-slate-500">
                暂无待执行或执行中的任务
              </div>
            ) : (
              <div className="space-y-6">
                {/* 执行中任务 */}
                {totalRunning > 0 && (
                  <div>
                    <h4 className="mb-3 text-sm font-semibold text-slate-700">
                      执行中 ({totalRunning})
                    </h4>
                    <div className="overflow-hidden rounded-lg border border-slate-200">
                      <table className="w-full border-collapse">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              ID
                            </th>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              网址
                            </th>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              状态
                            </th>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              创建时间
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {groupedTasks.running.map((task) => (
                            <tr
                              key={task.id}
                              className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                              onClick={() => setSelectedTask(task)}
                            >
                              <td className="p-2 text-sm text-slate-700">{task.id}</td>
                              <td className="p-2 text-sm text-slate-700">
                                <div className="max-w-[300px] truncate" title={task.url}>
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
                                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                                  {STATUS_LABELS[task.status as TaskStatus] || task.status}
                                </span>
                              </td>
                              <td className="p-2 text-sm text-slate-700">
                                {task.created_at
                                  ? formatDateTime(task.created_at)
                                  : "-"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* 待执行任务 */}
                {totalPending > 0 && (
                  <div>
                    <h4 className="mb-3 text-sm font-semibold text-slate-700">
                      待执行 ({totalPending})
                    </h4>
                    <div className="overflow-hidden rounded-lg border border-slate-200">
                      <table className="w-full border-collapse">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              ID
                            </th>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              网址
                            </th>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              状态
                            </th>
                            <th className="p-2 text-left text-xs font-medium text-slate-500">
                              创建时间
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {groupedTasks.pending.map((task) => (
                            <tr
                              key={task.id}
                              className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                              onClick={() => setSelectedTask(task)}
                            >
                              <td className="p-2 text-sm text-slate-700">{task.id}</td>
                              <td className="p-2 text-sm text-slate-700">
                                <div className="max-w-[300px] truncate" title={task.url}>
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
                                  {STATUS_LABELS[task.status as TaskStatus] || task.status}
                                </span>
                              </td>
                              <td className="p-2 text-sm text-slate-700">
                                {task.created_at
                                  ? formatDateTime(task.created_at)
                                  : "-"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 任务详情弹窗 */}
      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </>
  );
}

