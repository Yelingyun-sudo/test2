"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { BarChart3, Mail, CreditCard } from "lucide-react";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api";
import { useDateRange } from "@/lib/date-range-context";
import { ModuleKPICard } from "@/components/overview/module-kpi-card";
import { RecentTasksList } from "@/components/overview/recent-tasks-list";
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
  const { dateRange } = useDateRange();
  const [loading, setLoading] = useState(true);

  // Evidence 数据
  const [evidenceSummary, setEvidenceSummary] = useState<SummaryData | null>(null);
  const [evidenceRecentTasks, setEvidenceRecentTasks] = useState<EvidenceItem[]>([]);
  const [evidenceFailureTypes, setEvidenceFailureTypes] = useState<FailureTypeItem[]>([]);

  // Subscription 数据
  const [subscriptionSummary, setSubscriptionSummary] = useState<SummaryData | null>(null);
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
          evidenceRecentTasksRes,
          subscriptionSummaryRes,
          subscriptionRecentTasksRes
        ] = await Promise.all([
          apiFetch(`/evidence/stats/summary${queryString}`),
          apiFetch(`/evidence/stats/recent-tasks`),
          apiFetch(`/subscription/stats/summary${queryString}`),
          apiFetch(`/subscription/stats/recent-tasks`)
        ]);

        // 解析响应
        const [
          evidenceSummaryData,
          evidenceRecentTasksData,
          subscriptionSummaryData,
          subscriptionRecentTasksData
        ] = await Promise.all([
          evidenceSummaryRes.json(),
          evidenceRecentTasksRes.json() as Promise<{ recent_tasks: EvidenceItem[] }>,
          subscriptionSummaryRes.json(),
          subscriptionRecentTasksRes.json() as Promise<{ recent_tasks: SubscriptionItem[] }>
        ]);

        // 设置数据
        setEvidenceSummary(evidenceSummaryData.summary);
        setEvidenceRecentTasks(evidenceRecentTasksData.recent_tasks);
        setSubscriptionSummary(subscriptionSummaryData.summary);
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

  if (loading && !evidenceSummary && !subscriptionSummary) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
      </div>
    );
  }

  // 构建失败类型标签映射
  const evidenceFailureTypeLabel = evidenceFailureTypes.reduce((acc, item) => {
    acc[item.value] = item.label;
    return acc;
  }, {} as Record<string, string>);

  const subscriptionFailureTypeLabel = subscriptionFailureTypes.reduce((acc, item) => {
    acc[item.value] = item.label;
    return acc;
  }, {} as Record<string, string>);

  // 合并失败类型标签
  const allFailureTypeLabel = {
    ...evidenceFailureTypeLabel,
    ...subscriptionFailureTypeLabel
  };

  return (
    <div className="space-y-6">
      {/* 业务场景 KPI 概览区 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ModuleKPICard
          module="evidence"
          title="注册取证任务"
          icon={<BarChart3 className="h-5 w-5" />}
          summary={evidenceSummary}
          detailUrl="/evidence"
        />

        <ModuleKPICard
          module="subscription"
          title="订阅链接任务"
          icon={<Mail className="h-5 w-5" />}
          summary={subscriptionSummary}
          detailUrl="/subscription"
        />

        <ModuleKPICard
          module="payment"
          title="支付链接任务"
          icon={<CreditCard className="h-5 w-5" />}
          summary={null}
          detailUrl="/payment"
        />
      </div>

      {/* 最新任务列表区域 */}
      <RecentTasksList
        evidenceTasks={evidenceRecentTasks}
        subscriptionTasks={subscriptionRecentTasks}
        failureTypeLabel={allFailureTypeLabel}
      />
    </div>
  );
}
