"use client";

import { TaskQueueCard } from "@/components/common/task-queue-card";
import { type LucideIcon } from "lucide-react";

interface ModuleSectionProps {
  // 基本信息
  title: string;
  icon: LucideIcon;
  iconColor: string;

  // 主题颜色（仅用于占位符模式）
  themeColors?: {
    gradient?: string;
    border?: string;
  };

  // 队列数据
  summary: {
    pendingCount: number;
    runningCount: number;
  } | null;

  // 交互回调
  onStatusClick: (status: "running" | "pending") => void;

  // 子组件（已渲染好的 Chart 和 TaskList）
  chartNode?: React.ReactNode;
  taskListNode?: React.ReactNode;

  // 占位符模式
  isPlaceholder?: boolean;
  placeholderMessage?: string;
}

export function ModuleSection({
  title,
  icon: Icon,
  iconColor,
  themeColors,
  summary,
  onStatusClick,
  chartNode,
  taskListNode,
  isPlaceholder = false,
  placeholderMessage = "预计上线时间：2026年 Q1"
}: ModuleSectionProps) {
  // 占位符模式
  if (isPlaceholder) {
    return (
      <div className={`rounded-2xl border border-dashed p-6 shadow-sm ${themeColors?.border || "border-slate-300"} ${themeColors?.gradient || "bg-gradient-to-br from-slate-50 to-slate-100"}`}>
        {/* 标题 + 占位符卡片 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Icon className={`h-6 w-6 ${iconColor}`} />
            <h2 className="text-xl font-semibold text-slate-600">{title}</h2>
          </div>
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-2.5">
            <span className="text-sm text-slate-400">功能开发中</span>
          </div>
        </div>

        {/* 占位符内容 */}
        <div className="flex items-center justify-center h-[300px] rounded-xl bg-slate-50 border border-dashed border-slate-300">
          <div className="text-center">
            <div className="text-5xl mb-4">🚧</div>
            <div className="text-lg font-medium text-slate-600 mb-2">
              功能开发中，敬请期待
            </div>
            <div className="text-sm text-slate-500">{placeholderMessage}</div>
          </div>
        </div>
      </div>
    );
  }

  // 正常模式
  return (
    <div className="space-y-4">
      {/* 标题 + TaskQueueCard 横向 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Icon className={`h-6 w-6 ${iconColor}`} />
          <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
        </div>
        {summary && (
          <TaskQueueCard
            layout="horizontal"
            pendingCount={summary.pendingCount}
            runningCount={summary.runningCount}
            onStatusClick={onStatusClick}
          />
        )}
      </div>

      {/* 图表 + 任务列表 */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1">
          {chartNode}
        </div>
        <div className="lg:col-span-3">
          {taskListNode}
        </div>
      </div>
    </div>
  );
}
