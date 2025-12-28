"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface ModuleSummary {
  total_tasks: number;
  today_success_count: number;
  today_failed_count: number;
  success_rate?: number;
  running_count: number;
  pending_count: number;
}

interface ModuleSummaryCardProps {
  module: "evidence" | "subscription" | "payment";
  title: string;
  icon: React.ReactNode;
  summary?: ModuleSummary;
  detailUrl?: string;
  taskListComponent?: React.ReactNode;
  className?: string;
}

export function ModuleSummaryCard({
  module,
  title,
  icon,
  summary,
  detailUrl,
  taskListComponent,
  className
}: ModuleSummaryCardProps) {
  const handlePaymentClick = () => {
    toast.info("支付链接任务功能正在开发中", {
      description: "预计上线时间：2025年 Q2，敬请期待！",
      duration: 3000
    });
  };

  // 计算成功率
  const successRate = summary
    ? (
        (summary.today_success_count /
          (summary.today_success_count + summary.today_failed_count || 1)) *
        100
      ).toFixed(1)
    : "--";

  // 成功率颜色
  const successRateColor = summary
    ? parseFloat(successRate) >= 95
      ? "text-green-600"
      : parseFloat(successRate) >= 90
        ? "text-yellow-600"
        : "text-red-600"
    : "text-slate-400";

  const isPayment = module === "payment";

  return (
    <div
      className={cn(
        "rounded-2xl border bg-white p-6 shadow-sm",
        module === "evidence" && "border-blue-200",
        module === "subscription" && "border-purple-200",
        module === "payment" && "border-dashed border-slate-300 bg-slate-50",
        className
      )}
    >
      {/* 标题 */}
      <div className="mb-4 flex items-center gap-2">
        {icon}
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      </div>

      {/* 左右布局 */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-6">
        {/* 左侧：KPI 指标 */}
        <div className="space-y-4">
          {isPayment ? (
            // Payment 占位符
            <div className="space-y-3">
              <div className="text-sm text-slate-600">
                <span className="font-medium">期间任务:</span> --
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-medium">成功:</span> --{" "}
                <span className="ml-2">
                  <span className="font-medium">失败:</span> --
                </span>
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-medium">成功率:</span> --
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-medium">执行中:</span> --{" "}
                <span className="ml-2">
                  <span className="font-medium">待执行:</span> --
                </span>
              </div>

              <div className="mt-6 rounded-lg bg-slate-100 p-4 text-center">
                <div className="text-3xl mb-2">🚧</div>
                <div className="text-sm font-medium text-slate-700 mb-1">
                  功能开发中，敬请期待
                </div>
                <div className="text-xs text-slate-500">
                  预计上线时间：2025年 Q2
                </div>
              </div>

              <Button
                variant="outline"
                className="w-full"
                onClick={handlePaymentClick}
              >
                了解更多
              </Button>
            </div>
          ) : (
            // Evidence / Subscription KPI
            <>
              <div className="text-sm text-slate-600">
                <span className="font-medium">期间任务:</span>{" "}
                <span className="text-lg font-semibold text-slate-900">
                  {summary?.total_tasks.toLocaleString() ?? "--"}
                </span>
              </div>

              <div className="text-sm text-slate-600">
                <span className="font-medium">成功:</span>{" "}
                <span className="text-green-600 font-semibold">
                  {summary?.today_success_count.toLocaleString() ?? "--"}
                </span>
                <span className="mx-2">|</span>
                <span className="font-medium">失败:</span>{" "}
                <span className="text-red-600 font-semibold">
                  {summary?.today_failed_count.toLocaleString() ?? "--"}
                </span>
              </div>

              <div className="text-sm text-slate-600">
                <span className="font-medium">成功率:</span>{" "}
                <span className={cn("text-lg font-semibold", successRateColor)}>
                  {successRate}%
                </span>
                {summary && parseFloat(successRate) >= 90 && (
                  <span className="ml-2">🟢</span>
                )}
              </div>

              <div className="text-sm text-slate-600">
                <span className="font-medium">执行中:</span>{" "}
                <span className="text-amber-600 font-semibold">
                  {summary?.running_count ?? "--"}
                </span>
                <span className="mx-2">|</span>
                <span className="font-medium">待执行:</span>{" "}
                <span className="text-slate-700 font-semibold">
                  {summary?.pending_count ?? "--"}
                </span>
              </div>

              {detailUrl && (
                <Link href={detailUrl}>
                  <Button
                    variant="outline"
                    className="w-full mt-2 group"
                  >
                    查看详情
                    <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </Button>
                </Link>
              )}
            </>
          )}
        </div>

        {/* 右侧：任务列表或占位符 */}
        <div className="min-h-[200px]">
          {isPayment ? (
            <div className="h-full rounded-lg border border-dashed border-slate-300 bg-slate-50 flex items-center justify-center">
              <div className="text-center text-slate-400 text-sm">
                暂无任务数据
              </div>
            </div>
          ) : (
            taskListComponent
          )}
        </div>
      </div>
    </div>
  );
}
