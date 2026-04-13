"use client";

import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { CheckSquare, ListChecks, CreditCard } from "lucide-react";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api";
import { useDateRange } from "@/lib/date-range-context";
import { ModuleKPICard } from "@/components/overview/module-kpi-card";
import { RecentTasksList } from "@/components/overview/recent-tasks-list";
import type { EvidenceItem } from "@/types/evidence";
import type { SubscriptionItem } from "@/types/subscription";
import type { PaymentItem } from "@/types/payment";
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

  // Payment 数据
  const [paymentSummary, setPaymentSummary] = useState<SummaryData | null>(null);
  const [paymentRecentTasks, setPaymentRecentTasks] = useState<PaymentItem[]>([]);
  const [paymentFailureTypes, setPaymentFailureTypes] = useState<FailureTypeItem[]>([]);

  // 获取失败类型列表（只需获取一次）
  useEffect(() => {
    const fetchFailureTypes = async () => {
      try {
        const [evidenceRes, subscriptionRes, paymentRes] = await Promise.all([
          apiFetch("/evidence/failure-types"),
          apiFetch("/subscription/failure-types"),
          apiFetch("/payment/failure-types")
        ]);
        const [evidenceData, subscriptionData, paymentData] = await Promise.all([
          evidenceRes.json() as Promise<FailureTypesResponse>,
          subscriptionRes.json() as Promise<FailureTypesResponse>,
          paymentRes.json() as Promise<FailureTypesResponse>
        ]);
        setEvidenceFailureTypes(evidenceData.items);
        setSubscriptionFailureTypes(subscriptionData.items);
        setPaymentFailureTypes(paymentData.items);
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
          subscriptionRecentTasksRes,
          paymentSummaryRes,
          paymentRecentTasksRes
        ] = await Promise.all([
          apiFetch(`/evidence/stats/summary${queryString}`),
          apiFetch(`/evidence/stats/recent-tasks`),
          apiFetch(`/subscription/stats/summary${queryString}`),
          apiFetch(`/subscription/stats/recent-tasks`),
          apiFetch(`/payment/stats/summary${queryString}`),
          apiFetch(`/payment/stats/recent-tasks`)
        ]);

        // 解析响应
        const [
          evidenceSummaryData,
          evidenceRecentTasksData,
          subscriptionSummaryData,
          subscriptionRecentTasksData,
          paymentSummaryData,
          paymentRecentTasksData
        ] = await Promise.all([
          evidenceSummaryRes.json(),
          evidenceRecentTasksRes.json() as Promise<{ recent_tasks: EvidenceItem[] }>,
          subscriptionSummaryRes.json(),
          subscriptionRecentTasksRes.json() as Promise<{ recent_tasks: SubscriptionItem[] }>,
          paymentSummaryRes.json(),
          paymentRecentTasksRes.json() as Promise<{ recent_tasks: PaymentItem[] }>
        ]);

        // 设置数据
        setEvidenceSummary(evidenceSummaryData.summary);
        setEvidenceRecentTasks(evidenceRecentTasksData.recent_tasks);
        setSubscriptionSummary(subscriptionSummaryData.summary);
        setSubscriptionRecentTasks(subscriptionRecentTasksData.recent_tasks);
        setPaymentSummary(paymentSummaryData.summary);
        setPaymentRecentTasks(paymentRecentTasksData.recent_tasks);
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

  // 构建失败类型标签映射（使用 useMemo 确保在依赖项变化时才重新计算）
  // 注意：必须在所有条件返回之前调用 hooks，遵守 React Hooks 规则
  const allFailureTypeLabel = useMemo(() => {
    const evidenceFailureTypeLabel = evidenceFailureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);

    const subscriptionFailureTypeLabel = subscriptionFailureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);

    const paymentFailureTypeLabel = paymentFailureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);

    // 合并失败类型标签（后面的标签会覆盖前面的相同 key，但标签应该一致）
    return {
      ...evidenceFailureTypeLabel,
      ...subscriptionFailureTypeLabel,
      ...paymentFailureTypeLabel
    };
  }, [evidenceFailureTypes, subscriptionFailureTypes, paymentFailureTypes]);

  if (loading && !evidenceSummary && !subscriptionSummary && !paymentSummary) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 业务场景 KPI 概览区 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ModuleKPICard
          module="evidence"
          title="注册取证任务"
          icon={<CheckSquare className="h-5 w-5" />}
          summary={evidenceSummary}
          detailUrl="/evidence"
          dateRange={dateRange}
        />

        <ModuleKPICard
          module="subscription"
          title="订阅链接任务"
          icon={<ListChecks className="h-5 w-5" />}
          summary={subscriptionSummary}
          detailUrl="/subscription"
          dateRange={dateRange}
        />

        <ModuleKPICard
          module="payment"
          title="支付链接任务"
          icon={<CreditCard className="h-5 w-5" />}
          summary={paymentSummary}
          detailUrl="/payment"
          dateRange={dateRange}
        />
      </div>

      {/* 最新任务列表区域 */}
      <RecentTasksList
        evidenceTasks={evidenceRecentTasks}
        subscriptionTasks={subscriptionRecentTasks}
        paymentTasks={paymentRecentTasks}
        failureTypeLabel={allFailureTypeLabel}
      />
    </div>
  );
}
