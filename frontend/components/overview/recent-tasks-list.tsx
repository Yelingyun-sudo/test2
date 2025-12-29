"use client";

import { useState, useMemo } from "react";
import { ChevronDown, ChevronUp, List, CheckSquare, ListChecks, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDateTime, formatDurationSeconds } from "@/lib/datetime";
import { cn } from "@/lib/utils";
import { TaskDetailModal as EvidenceTaskDetailModal } from "@/components/evidence/task-detail-modal";
import { TaskDetailModal as SubscriptionTaskDetailModal } from "@/components/subscription/task-detail-modal";
import type { EvidenceItem } from "@/types/evidence";
import type { SubscriptionItem } from "@/types/subscription";
import { STATUS_LABELS, STATUS_STYLES, type TaskStatus } from "@/types/common";

interface RecentTask {
  id: number;
  module: "evidence" | "subscription";
  moduleLabel: string;
  status: string;
  url: string;
  executed_at: string | null;
  duration_seconds: number | null;
  result: string | null;
  failure_type: string | null;
}

interface RecentTasksListProps {
  evidenceTasks: EvidenceItem[];
  subscriptionTasks: SubscriptionItem[];
  failureTypeLabel?: Record<string, string>;
}

export function RecentTasksList({
  evidenceTasks,
  subscriptionTasks,
  failureTypeLabel = {}
}: RecentTasksListProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [selectedTaskType, setSelectedTaskType] = useState<string>("all");
  const [selectedTaskStatus, setSelectedTaskStatus] = useState<string>("all");
  const [selectedTask, setSelectedTask] = useState<{
    type: "evidence" | "subscription";
    task: EvidenceItem | SubscriptionItem;
  } | null>(null);

  // 合并任务并添加模块标识
  const allMergedTasks: RecentTask[] = useMemo(() => {
    return [
      ...evidenceTasks.map((task) => ({
        id: task.id,
        module: "evidence" as const,
        moduleLabel: "注册取证任务",
        status: task.status,
        url: task.url,
        executed_at: task.executed_at || null,
        duration_seconds: task.duration_seconds || null,
        result: task.result || null,
        failure_type: task.failure_type || null
      })),
      ...subscriptionTasks.map((task) => ({
        id: task.id,
        module: "subscription" as const,
        moduleLabel: "订阅链接任务",
        status: task.status,
        url: task.url,
        executed_at: task.executed_at || null,
        duration_seconds: task.duration_seconds || null,
        result: task.result || null,
        failure_type: task.failure_type || null
      }))
    ]
      .sort((a, b) => {
        // 按执行时间排序，执行中的任务优先
        if (a.status === "RUNNING" && b.status !== "RUNNING") return -1;
        if (a.status !== "RUNNING" && b.status === "RUNNING") return 1;
        
        // 按执行时间倒序
        if (a.executed_at && b.executed_at) {
          return new Date(b.executed_at).getTime() - new Date(a.executed_at).getTime();
        }
        if (a.executed_at) return -1;
        if (b.executed_at) return 1;
        
        return b.id - a.id;
      });
  }, [evidenceTasks, subscriptionTasks]);

  // 应用过滤条件
  const mergedTasks: RecentTask[] = useMemo(() => {
    let filtered = allMergedTasks;

    // 任务类型过滤
    if (selectedTaskType !== "all") {
      if (selectedTaskType === "payment") {
        // 支付链接任务目前无数据，返回空数组
        filtered = [];
      } else {
        filtered = filtered.filter((task) => task.module === selectedTaskType);
      }
    }

    // 任务状态过滤
    if (selectedTaskStatus !== "all") {
      filtered = filtered.filter((task) => task.status === selectedTaskStatus);
    }

    return filtered.slice(0, 9); // 取前9个（3x3网格）
  }, [allMergedTasks, selectedTaskType, selectedTaskStatus]);

  const handleTaskClick = (task: RecentTask) => {
    if (task.module === "evidence") {
      const evidenceTask = evidenceTasks.find((t) => t.id === task.id);
      if (evidenceTask) {
        setSelectedTask({ type: "evidence", task: evidenceTask });
      }
    } else {
      const subscriptionTask = subscriptionTasks.find((t) => t.id === task.id);
      if (subscriptionTask) {
        setSelectedTask({ type: "subscription", task: subscriptionTask });
      }
    }
  };

  const getStatusIcon = (status: string): JSX.Element | null => {
    switch (status) {
      case "SUCCESS":
        return <span className="mr-1">✅</span>;
      case "FAILED":
        return <span className="mr-1">❌</span>;
      case "RUNNING":
        return <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />;
      case "PENDING":
        return <span className="mr-1">⏸️</span>;
      default:
        return <span className="mr-1">•</span>;
    }
  };

  const getModuleIcon = (module: "evidence" | "subscription") => {
    return module === "evidence" ? (
      <CheckSquare className="h-4 w-4" />
    ) : (
      <ListChecks className="h-4 w-4" />
    );
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      {/* 标题栏 */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <List className="h-5 w-5 text-slate-600" />
          <h3 className="text-lg font-semibold text-slate-900">最新任务列表</h3>
          {!isExpanded && mergedTasks.length > 0 && (
            <span className="text-sm text-slate-500">
              （共 {mergedTasks.length} 个任务）
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* 任务类型过滤器 */}
          <Select value={selectedTaskType} onValueChange={setSelectedTaskType}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="任务类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">所有任务</SelectItem>
              <SelectItem value="evidence">注册取证任务</SelectItem>
              <SelectItem value="subscription">订阅链接任务</SelectItem>
              <SelectItem value="payment">支付链接任务</SelectItem>
            </SelectContent>
          </Select>

          {/* 任务状态过滤器 */}
          <Select value={selectedTaskStatus} onValueChange={setSelectedTaskStatus}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="任务状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">所有状态</SelectItem>
              <SelectItem value="SUCCESS">成功</SelectItem>
              <SelectItem value="FAILED">失败</SelectItem>
              <SelectItem value="RUNNING">执行中</SelectItem>
            </SelectContent>
          </Select>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-slate-600 hover:text-slate-900"
          >
            {isExpanded ? (
              <>
                收起
                <ChevronUp className="ml-1 h-4 w-4" />
              </>
            ) : (
              <>
                展开
                <ChevronDown className="ml-1 h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 任务列表 */}
      {isExpanded && (
        <div className="mt-4 transition-all duration-300">
          {mergedTasks.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">
              暂无最新任务
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {mergedTasks.map((task) => (
                <div
                  key={`${task.module}-${task.id}`}
                  onClick={() => handleTaskClick(task)}
                  className={cn(
                    "rounded-lg border border-slate-200 p-4 cursor-pointer",
                    "hover:shadow-md hover:border-slate-300 transition-all duration-200",
                    "bg-white"
                  )}
                >
                  {/* 任务头部 */}
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        "flex-shrink-0",
                        task.module === "evidence" ? "text-blue-600" : "text-purple-600"
                      )}>
                        {getModuleIcon(task.module)}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-900">
                          {task.moduleLabel}
                        </div>
                        <div className="text-xs text-slate-500">
                          #{task.id}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {task.status === "FAILED" && task.failure_type && (
                        <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10">
                          {failureTypeLabel[task.failure_type] || task.failure_type}
                        </span>
                      )}
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
                          STATUS_STYLES[task.status as TaskStatus] ||
                            "bg-slate-100 text-slate-600 border border-slate-200"
                        )}
                      >
                        {getStatusIcon(task.status)}
                        {STATUS_LABELS[task.status as TaskStatus] || task.status}
                      </span>
                    </div>
                  </div>

                  {/* 任务信息 */}
                  <div className="space-y-1 text-xs text-slate-600">
                    {task.executed_at && (
                      <div>
                        时间: {formatDateTime(task.executed_at)}
                      </div>
                    )}
                    {task.duration_seconds !== null && task.status !== "RUNNING" && task.status !== "PENDING" && (
                      <div>
                        耗时: {formatDurationSeconds(task.duration_seconds)}
                      </div>
                    )}
                    <div className="truncate" title={task.url}>
                      网址: {task.url}
                    </div>
                    {task.result && (
                      <div className="mt-2 truncate" title={task.result}>
                        结果: {task.result}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 任务详情弹窗 */}
      {selectedTask && (
        selectedTask.type === "evidence" ? (
          <EvidenceTaskDetailModal
            task={selectedTask.task as EvidenceItem}
            onClose={() => setSelectedTask(null)}
            failureTypeLabel={failureTypeLabel}
          />
        ) : (
          <SubscriptionTaskDetailModal
            task={selectedTask.task as SubscriptionItem}
            onClose={() => setSelectedTask(null)}
            failureTypeLabel={failureTypeLabel}
          />
        )
      )}
    </div>
  );
}

