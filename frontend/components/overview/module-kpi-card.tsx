"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatDurationSeconds } from "@/lib/datetime";
import { formatTokenCount } from "@/lib/utils";
import { type DateRange, getDateRangeLabel } from "@/components/ui/date-range-picker";
import { Badge } from "@/components/ui/badge";

interface ModuleSummaryData {
  total_tasks: number;
  pending_count: number;
  running_count: number;
  today_success_count: number;
  today_failed_count: number;
  today_tokens: number;
  today_avg_success_duration_seconds: number;
  today_avg_failed_duration_seconds: number;
}

interface ModuleKPICardProps {
  module: "evidence" | "subscription" | "payment";
  title: string;
  icon: React.ReactNode;
  summary?: ModuleSummaryData | null;
  detailUrl: string;
  className?: string;
  dateRange?: DateRange;
}

export function ModuleKPICard({
  module,
  title,
  icon,
  summary,
  detailUrl,
  className,
  dateRange
}: ModuleKPICardProps) {
  // 根据日期范围生成标签
  const dateRangeLabel = dateRange ? getDateRangeLabel(dateRange) : "总计";
  const taskCountLabel = `${dateRangeLabel}执行`;

  // 计算成功率
  const successCount = summary?.today_success_count || 0;
  const failedCount = summary?.today_failed_count || 0;
  const totalCompleted = successCount + failedCount;
  const successRate =
    totalCompleted > 0
      ? ((successCount / totalCompleted) * 100).toFixed(1)
      : "--";

  // 成功率颜色和状态图标
  const getSuccessRateStyle = () => {
    if (successRate === "--") return { color: "text-slate-400", icon: null };
    const rate = parseFloat(successRate);
    if (rate >= 60) return { color: "text-emerald-600", icon: null };
    if (rate >= 40) return { color: "text-slate-700", icon: null };
    return { color: "text-slate-600", icon: null };
  };

  const successRateStyle = getSuccessRateStyle();

  // 计算平均时长（优先使用成功任务的平均时长）
  const avgDuration =
    summary?.today_avg_success_duration_seconds ??
    summary?.today_avg_failed_duration_seconds ??
    null;

  // 模块颜色方案
  const getModuleStyles = () => {
    switch (module) {
      case "evidence":
        return {
          bg: "bg-gradient-to-br from-sky-500/10 to-sky-600/10",
          border: "border-sky-100",
          iconColor: "text-sky-600"
        };
      case "subscription":
        return {
          bg: "bg-gradient-to-br from-emerald-500/10 to-emerald-600/10",
          border: "border-emerald-100",
          iconColor: "text-emerald-600"
        };
      case "payment":
        return {
          bg: "bg-gradient-to-br from-violet-100 to-violet-200/60",
          border: "border-purple-100",
          iconColor: "text-violet-600"
        };
    }
  };

  const moduleStyles = getModuleStyles();

  return (
    <div
      className={cn(
        "rounded-2xl border p-6 shadow-sm backdrop-blur transition-all duration-300 hover:shadow-xl hover:scale-[1.02]",
        moduleStyles.bg,
        moduleStyles.border,
        className
      )}
    >
      {/* 顶部：图标 + 标题 */}
      <div className="mb-4 flex items-center gap-2">
        <div className={cn("flex-shrink-0", moduleStyles.iconColor)}>
          {icon}
        </div>
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      </div>

      <>
        {/* 主要指标区域：总任务数 + 成功率 */}
          <div className="mb-4 grid grid-cols-2 gap-4">
            <div>
              <div className="text-4xl font-bold text-slate-900">
                {summary?.total_tasks.toLocaleString() ?? "--"}
              </div>
              <div className="text-sm mt-1 flex items-center gap-1.5">
                <Badge className="bg-white/60 backdrop-blur-sm text-slate-700 border-white/80 shadow-sm hover:bg-white/70">
                  {dateRangeLabel}
                </Badge>
                <span className="text-slate-300">·</span>
                <span className="font-medium text-slate-700">执行</span>
              </div>
            </div>
            <div className="text-right">
              <div
                className={cn(
                  "text-2xl font-bold",
                  successRateStyle.color
                )}
              >
                {successRate}%
                {successRateStyle.icon && (
                  <span className="ml-1 text-base">
                    {successRateStyle.icon}
                  </span>
                )}
              </div>
              <div className="text-sm mt-1 flex items-center justify-end gap-1.5">
                <Badge className="bg-white/60 backdrop-blur-sm text-slate-700 border-white/80 shadow-sm hover:bg-white/70">
                  {dateRangeLabel}
                </Badge>
                <span className="text-slate-300">·</span>
                <span className="font-medium text-slate-700">成功率</span>
              </div>
            </div>
          </div>

          {/* 细分指标区域：成功/失败，执行中/待执行 */}
          <div className="mb-4 space-y-2 rounded-lg bg-white/60 p-3">
            <div className="grid grid-cols-5 items-center gap-x-2 text-sm">
              <span className="text-slate-600">成功:</span>
              <span className="font-semibold text-green-600 text-right">
                {successCount.toLocaleString()}
              </span>
              <span className="text-slate-400 text-center">|</span>
              <span className="text-slate-600">失败:</span>
              <span className="font-semibold text-red-600 text-right">
                {failedCount.toLocaleString()}
              </span>
            </div>
            <div className="grid grid-cols-5 items-center gap-x-2 text-sm">
              <span className="text-slate-600">执行中:</span>
              <span className="font-semibold text-amber-600 text-right">
                {summary?.running_count ?? "--"}
              </span>
              <span className="text-slate-400 text-center">|</span>
              <span className="text-slate-600">待执行:</span>
              <span className="font-semibold text-slate-700 text-right">
                {summary?.pending_count ?? "--"}
              </span>
            </div>
          </div>

          {/* 辅助信息区域：Token + 平均时长 */}
          <div className="mb-4 flex items-center justify-between text-sm">
            <div className="flex items-center gap-1">
              <span className="text-slate-600">Token:</span>
              <span className="font-medium text-slate-900">
                {formatTokenCount(summary?.today_tokens)}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-slate-600">平均时长:</span>
              <span className="font-medium text-slate-900">
                {formatDurationSeconds(avgDuration)}
              </span>
            </div>
          </div>

          {/* 底部操作按钮 */}
          <Link href={detailUrl}>
            <Button
              variant="outline"
              className="w-full group"
            >
              查看详情
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Button>
          </Link>
      </>
    </div>
  );
}

