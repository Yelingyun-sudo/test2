"use client";

import { useEffect, useState, useMemo } from "react";
import { format } from "date-fns";
import { useRouter } from "next/navigation";
import { BarChart3, Mail, CreditCard } from "lucide-react";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api";
import { useDateRange } from "@/lib/date-range-context";
import { ModuleSection } from "@/components/overview/module-section";
import { DailyTrendStackedBarChart as EvidenceDailyTrendChart } from "@/components/overview/daily-trend-stacked-bar-chart";
import { TaskListRecent as EvidenceTaskListRecent } from "@/components/evidence/task-list-recent";
import { DailyTrendStackedBarChart as SubscriptionDailyTrendChart } from "@/components/overview/daily-trend-stacked-bar-chart";
import { TaskListRecent as SubscriptionTaskListRecent } from "@/components/subscription/task-list-recent";
import type { DailyTrendItem, DailyTrendResponse, RecentTasksResponse } from "@/lib/types";
import type { EvidenceItem } from "@/types/evidence";
import type { SubscriptionItem } from "@/types/subscription";
import type { FailureTypeItem, FailureTypesResponse } from "@/types/common";

interface SummaryData {
  total_tasks: number;
  pending_count: number;
  running_count: number;
  today_success_count: number;
  today_failed_count: number;
  today_tokens: number;
  today_avg_success_tokens: number;
  today_avg_failed_tokens: number;
  today_avg_success_duration_seconds: number;
  today_avg_failed_duration_seconds: number;
}

export function SystemOverview() {
  const router = useRouter();
  const { dateRange, setDateRange } = useDateRange();
  const [loading, setLoading] = useState(true);

  // Evidence 数据
  const [evidenceSummary, setEvidenceSummary] = useState<SummaryData | null>(null);
  const [evidenceDailyTrend, setEvidenceDailyTrend] = useState<DailyTrendItem[]>([]);
  const [evidenceRecentTasks, setEvidenceRecentTasks] = useState<EvidenceItem[]>([]);
  const [evidenceFailureTypes, setEvidenceFailureTypes] = useState<FailureTypeItem[]>([]);

  // Subscription 数据
  const [subscriptionSummary, setSubscriptionSummary] = useState<SummaryData | null>(null);
  const [subscriptionDailyTrend, setSubscriptionDailyTrend] = useState<DailyTrendItem[]>([]);
  const [subscriptionRecentTasks, setSubscriptionRecentTasks] = useState<SubscriptionItem[]>([]);
  const [subscriptionFailureTypes, setSubscriptionFailureTypes] = useState<FailureTypeItem[]>([]);

  // 获取失败类型列表（只需获取一次）
  useEffect(() => {
    const fetchFailureTypes = async () => {
      try {
        const [evidenceRes, subscriptionRes] = await Promise.all([
          apiFetch("/evidence/failure-types"),
          apiFetch("/subscription/failure-types")
        ]);
        const [evidenceData, subscriptionData] = await Promise.all([
          evidenceRes.json() as Promise<FailureTypesResponse>,
          subscriptionRes.json() as Promise<FailureTypesResponse>
        ]);
        setEvidenceFailureTypes(evidenceData.items);
        setSubscriptionFailureTypes(subscriptionData.items);
      } catch (error) {
        console.error("获取失败类型列表失败:", error);
      }
    };
    fetchFailureTypes();
  }, []);

  // 获取数据（受 dateRange 影响，包含轮询）
  useEffect(() => {
    const fetchOverviewData = async () => {
      setLoading(true);
      try {
        // 构建查询参数
        const params = new URLSearchParams();
        if (dateRange.from && dateRange.to) {
          params.set("start_date", format(dateRange.from, "yyyy-MM-dd"));
          params.set("end_date", format(dateRange.to, "yyyy-MM-dd"));
        }

        const queryString = params.toString() ? `?${params}` : "";

        // 并发调用所有 API
        const [
          evidenceSummaryRes,
          evidenceDailyTrendRes,
          evidenceRecentTasksRes,
          subscriptionSummaryRes,
          subscriptionDailyTrendRes,
          subscriptionRecentTasksRes
        ] = await Promise.all([
          apiFetch(`/evidence/stats/summary${queryString}`),
          apiFetch(`/evidence/stats/daily-trend`),
          apiFetch(`/evidence/stats/recent-tasks`),
          apiFetch(`/subscription/stats/summary${queryString}`),
          apiFetch(`/subscription/stats/daily-trend`),
          apiFetch(`/subscription/stats/recent-tasks`)
        ]);

        // 解析响应
        const [
          evidenceSummaryData,
          evidenceDailyTrendData,
          evidenceRecentTasksData,
          subscriptionSummaryData,
          subscriptionDailyTrendData,
          subscriptionRecentTasksData
        ] = await Promise.all([
          evidenceSummaryRes.json(),
          evidenceDailyTrendRes.json() as Promise<DailyTrendResponse>,
          evidenceRecentTasksRes.json() as Promise<{ recent_tasks: EvidenceItem[] }>,
          subscriptionSummaryRes.json(),
          subscriptionDailyTrendRes.json() as Promise<DailyTrendResponse>,
          subscriptionRecentTasksRes.json() as Promise<{ recent_tasks: SubscriptionItem[] }>
        ]);

        // 设置数据
        setEvidenceSummary(evidenceSummaryData.summary);
        setEvidenceDailyTrend(evidenceDailyTrendData.daily_trend);
        setEvidenceRecentTasks(evidenceRecentTasksData.recent_tasks);
        setSubscriptionSummary(subscriptionSummaryData.summary);
        setSubscriptionDailyTrend(subscriptionDailyTrendData.daily_trend);
        setSubscriptionRecentTasks(subscriptionRecentTasksData.recent_tasks);
      } catch (error) {
        console.error("Failed to fetch overview data:", error);
        toast.error("加载概览数据失败");
      } finally {
        setLoading(false);
      }
    };

    fetchOverviewData();

    // 每 30 秒轮询一次
    const interval = setInterval(fetchOverviewData, 30000);
    return () => clearInterval(interval);
  }, [dateRange]);

  // 构建失败类型标签映射
  const evidenceFailureTypeLabel = useMemo(() => {
    return evidenceFailureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);
  }, [evidenceFailureTypes]);

  const subscriptionFailureTypeLabel = useMemo(() => {
    return subscriptionFailureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);
  }, [subscriptionFailureTypes]);

  if (loading && !evidenceSummary && !subscriptionSummary) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Evidence 模块 */}
      <ModuleSection
        title="注册取证任务"
        icon={BarChart3}
        iconColor="text-blue-600"
        summary={
          evidenceSummary
            ? {
                pendingCount: evidenceSummary.pending_count,
                runningCount: evidenceSummary.running_count
              }
            : null
        }
        onStatusClick={(status) => router.push(`/evidence?status=${status}`)}
        chartNode={
          <EvidenceDailyTrendChart
            dailyTrend={evidenceDailyTrend}
            days={5}
            onDateClick={(date) => {
              const selectedDate = new Date(date);
              setDateRange({ from: selectedDate, to: selectedDate });
              router.push("/evidence");
            }}
          />
        }
        taskListNode={
          <EvidenceTaskListRecent
            tasks={evidenceRecentTasks}
            total={evidenceSummary?.total_tasks || 0}
            failureTypeLabel={evidenceFailureTypeLabel}
            onTaskClick={() => router.push("/evidence")}
            onViewAll={() => router.push("/evidence")}
          />
        }
      />

      {/* Subscription 模块 */}
      <ModuleSection
        title="订阅链接任务"
        icon={Mail}
        iconColor="text-purple-600"
        summary={
          subscriptionSummary
            ? {
                pendingCount: subscriptionSummary.pending_count,
                runningCount: subscriptionSummary.running_count
              }
            : null
        }
        onStatusClick={(status) => router.push(`/subscription?status=${status}`)}
        chartNode={
          <SubscriptionDailyTrendChart
            dailyTrend={subscriptionDailyTrend}
            days={5}
            onDateClick={(date) => {
              const selectedDate = new Date(date);
              setDateRange({ from: selectedDate, to: selectedDate });
              router.push("/subscription");
            }}
          />
        }
        taskListNode={
          <SubscriptionTaskListRecent
            tasks={subscriptionRecentTasks}
            total={subscriptionSummary?.total_tasks || 0}
            failureTypeLabel={subscriptionFailureTypeLabel}
            onTaskClick={() => router.push("/subscription")}
            onViewAll={() => router.push("/subscription")}
          />
        }
      />

      {/* Payment 模块 - 占位符 */}
      <ModuleSection
        title="支付链接任务"
        icon={CreditCard}
        iconColor="text-slate-400"
        themeColors={{
          gradient: "bg-gradient-to-br from-slate-50 to-slate-100",
          border: "border-slate-300"
        }}
        summary={null}
        onStatusClick={() => {}}
        isPlaceholder
        placeholderMessage="预计上线时间：2026年 Q1"
      />
    </div>
  );
}
