"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  CartesianGrid,
  Cell,
  Bar,
  BarChart,
  PieChart,
  Pie,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { TaskQueueCard } from "@/components/common/task-queue-card";
import { TaskListRecent } from "@/components/evidence/task-list-recent";
import { TaskListDrawer } from "@/components/evidence/task-list-drawer";
import { TaskDetailModal } from "@/components/evidence/task-detail-modal";
import { type DateRange, getTimeRangeLabel } from "@/components/ui/date-range-picker";
import { format } from "date-fns";
import { DailyTrendChart } from "@/components/evidence/daily-trend-chart";
import { DashboardShell } from "./shell";
import { apiFetch } from "@/lib/api";
import { formatDurationSeconds } from "@/lib/datetime";
import { formatTokenCount } from "@/lib/utils";
import { useDateRange } from "@/lib/date-range-context";
import { toast } from "sonner";
import type {
  EvidenceStatsResponse,
  EvidenceSummaryResponse,
  EvidenceDailyTrendResponse,
  EvidenceStatusDistributionResponse,
  EvidenceRecentTasksResponse,
  EvidenceFailureTypesStatsResponse
} from "@/lib/types";
import { STATUS_LABELS, STATUS_COLORS_ENHANCED, type TaskStatus, type FailureTypeItem, type FailureTypesResponse } from "@/types/common";
import type { EvidenceItem } from "@/types/evidence";

type DashboardProps = {
  onLogout: () => void;
  account?: string;
};

export function EvidenceDashboard({ onLogout, account }: DashboardProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const { dateRange: statsTimeRange, setDateRange } = useDateRange();

  const [stats, setStats] = useState<EvidenceStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [isTaskListDrawerOpen, setIsTaskListDrawerOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<EvidenceItem | null>(null);
  const [failureTypes, setFailureTypes] = useState<FailureTypeItem[]>([]);

  useEffect(() => {
    const hasQueryParams =
      searchParams.get("page") ||
      searchParams.get("status") ||
      searchParams.get("failure_type") ||
      searchParams.get("q");

    if (hasQueryParams) {
      setIsTaskListDrawerOpen(true);
    }
  }, [searchParams]);

  const handleDateClick = (date: string) => {
    const selectedDate = new Date(date);
    setDateRange({ from: selectedDate, to: selectedDate });
    
    // 将日期参数添加到 URL 中，以便抽屉窗口能够读取并显示
    const params = new URLSearchParams();
    params.set("start_date", format(selectedDate, "yyyy-MM-dd"));
    params.set("end_date", format(selectedDate, "yyyy-MM-dd"));
    router.push(`/evidence?${params.toString()}`);
    
    setIsTaskListDrawerOpen(true);
  };

  useEffect(() => {
    async function fetchStats() {
      try {
        const params = new URLSearchParams();
        if (statsTimeRange.from && statsTimeRange.to) {
          params.set("start_date", format(statsTimeRange.from, "yyyy-MM-dd"));
          params.set("end_date", format(statsTimeRange.to, "yyyy-MM-dd"));
        }
        const dateRangeParam = params.toString() ? `?${params.toString()}` : "";

        const [summaryRes, dailyTrendRes, statusDistRes, recentTasksRes, failureTypesRes] =
          await Promise.all([
            apiFetch(`/evidence/stats/summary${dateRangeParam}`),
            apiFetch(`/evidence/stats/daily-trend`),
            apiFetch(`/evidence/stats/status-distribution${dateRangeParam}`),
            apiFetch(`/evidence/stats/recent-tasks`),
            apiFetch(`/evidence/stats/failure-types${dateRangeParam}`),
          ]);

        const [summaryData, dailyTrendData, statusDistData, recentTasksData, failureTypesData] =
          await Promise.all([
            summaryRes.json() as Promise<EvidenceSummaryResponse>,
            dailyTrendRes.json() as Promise<EvidenceDailyTrendResponse>,
            statusDistRes.json() as Promise<EvidenceStatusDistributionResponse>,
            recentTasksRes.json() as Promise<EvidenceRecentTasksResponse>,
            failureTypesRes.json() as Promise<EvidenceFailureTypesStatsResponse>,
          ]);

        setStats({
          summary: summaryData.summary,
          daily_trend: dailyTrendData.daily_trend,
          status_distribution: statusDistData.status_distribution,
          recent_tasks: recentTasksData.recent_tasks,
          failure_type_distribution: failureTypesData.failure_type_distribution,
          failure_summary: failureTypesData.failure_summary,
        });
      } catch (error) {
        toast.error("加载统计数据失败");
        console.error(error);
      } finally {
        setLoading(false);
      }
    }

    fetchStats();

    const interval = setInterval(() => {
      fetchStats();
    }, 30000);

    return () => clearInterval(interval);
  }, [statsTimeRange]);

  useEffect(() => {
    const fetchFailureTypes = async () => {
      try {
        const res = await apiFetch("/evidence/failure-types");
        if (!res.ok) {
          throw new Error("获取失败类型列表失败");
        }
        const data = (await res.json()) as FailureTypesResponse;
        setFailureTypes(data.items);
      } catch (error) {
        console.error("获取失败类型列表失败:", error);
        toast.error("获取失败类型列表失败");
      }
    };
    fetchFailureTypes();
  }, []);

  const failureTypeLabel: Record<string, string> = useMemo(() => {
    return failureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);
  }, [failureTypes]);

  // 根据时间范围生成 KPI 卡片标题前缀
  const timeRangeLabel = getTimeRangeLabel(statsTimeRange);

  if (loading) {
    return (
      <DashboardShell
        account={account}
        onLogout={onLogout}
      >
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
        </div>
      </DashboardShell>
    );
  }

  if (!stats) {
    return (
      <DashboardShell
        account={account}
        onLogout={onLogout}
      >
        <div className="text-center py-20 text-slate-500">暂无任务数据</div>
      </DashboardShell>
    );
  }

  const { summary, status_distribution } = stats;

  const completedStatusDistribution = status_distribution.filter(
    (item) => item.status === "SUCCESS" || item.status === "FAILED"
  );

  const totalCompletedCount = completedStatusDistribution.reduce((sum, item) => sum + item.count, 0);
  const distributionData = completedStatusDistribution.map((item) => ({
    name: STATUS_LABELS[item.status as TaskStatus] || item.status,
    value: item.count,
    color: STATUS_COLORS_ENHANCED[item.status as TaskStatus] || "#94a3b8",
    percentage: totalCompletedCount > 0 ? ((item.count / totalCompletedCount) * 100).toFixed(1) : 0,
    status: item.status
  }));

  const successCount = distributionData.find(item => item.status === "SUCCESS")?.value || 0;
  const failedCount = distributionData.find(item => item.status === "FAILED")?.value || 0;

  const totalExecuted = summary.today_success_count + summary.today_failed_count;
  const avgDurationSeconds = totalExecuted > 0
    ? (summary.today_success_count * summary.today_avg_success_duration_seconds +
       summary.today_failed_count * summary.today_avg_failed_duration_seconds) / totalExecuted
    : null;

  const timeRangeSuccessCount = summary.today_success_count;
  const timeRangeFailedCount = summary.today_failed_count;
  const timeRangeTotalCompleted = timeRangeSuccessCount + timeRangeFailedCount;
  const timeRangeSuccessRate = timeRangeTotalCompleted > 0
    ? (timeRangeSuccessCount / timeRangeTotalCompleted)
    : 0.0;

  return (
    <DashboardShell
      account={account}
      onLogout={onLogout}
    >
      <section className="space-y-4">
        <div className="grid gap-4 md:grid-cols-5">
          {/* 已执行 */}
          <div className="rounded-2xl border bg-gradient-to-br from-sky-500/10 to-sky-600/10 text-sky-700 border-sky-100 p-5 shadow-sm backdrop-blur">
            <p className="text-sm text-slate-600">{timeRangeLabel}执行</p>
            <div className="mt-2 flex items-baseline gap-3">
              <div className="text-3xl font-semibold">
                {summary.today_success_count + summary.today_failed_count}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-xs text-slate-600">总计</span>
                <span className="text-base text-slate-600">
                  {formatTokenCount(summary.today_tokens)}
                </span>
                <span className="text-xs text-slate-600">token</span>
              </div>
            </div>
            <div className="mt-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                <span className="h-2 w-2 rounded-full bg-violet-400/60" />
                平均耗时：{formatDurationSeconds(avgDurationSeconds)}
              </div>
            </div>
          </div>

          {/* 成功 */}
          <div className="rounded-2xl border bg-gradient-to-br from-emerald-500/10 to-emerald-600/10 text-emerald-700 border-emerald-100 p-5 shadow-sm backdrop-blur">
            <p className="text-sm text-slate-600">{timeRangeLabel}成功</p>
            <div className="mt-2 flex items-baseline gap-3">
              <div className="text-3xl font-semibold text-emerald-700">
                {summary.today_success_count}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-xs text-slate-600">平均</span>
                <span className="text-base text-slate-600">
                  {formatTokenCount(summary.today_avg_success_tokens)}
                </span>
                <span className="text-xs text-slate-600">Token</span>
              </div>
            </div>
            <div className="mt-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                <span className="h-2 w-2 rounded-full bg-emerald-400/60" />
                平均耗时：{formatDurationSeconds(summary.today_avg_success_duration_seconds)}
              </div>
            </div>
          </div>

          {/* 失败 */}
          <div className="rounded-2xl border bg-gradient-to-br from-rose-500/10 to-rose-600/10 text-rose-700 border-rose-100 p-5 shadow-sm backdrop-blur">
            <p className="text-sm text-slate-600">{timeRangeLabel}失败</p>
            <div className="mt-2 flex items-baseline gap-3">
              <div className="text-3xl font-semibold text-rose-700">
                {summary.today_failed_count}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-xs text-slate-600">平均</span>
                <span className="text-base text-slate-600">
                  {formatTokenCount(summary.today_avg_failed_tokens)}
                </span>
                <span className="text-xs text-slate-600">Token</span>
              </div>
            </div>
            <div className="mt-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                <span className="h-2 w-2 rounded-full bg-rose-400/60" />
                平均耗时：{formatDurationSeconds(summary.today_avg_failed_duration_seconds)}
              </div>
            </div>
          </div>

          {/* 成功率 */}
          <div className="rounded-2xl border bg-gradient-to-br from-violet-100 to-violet-200/60 border-purple-100 p-5 shadow-sm">
            <p className="text-sm text-[#555555]">{timeRangeLabel}成功率</p>
            <div className="mt-2">
              <div className="text-3xl font-semibold text-[#5232D9]">
                {(timeRangeSuccessRate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="mt-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600">
                <span className="h-2 w-2 rounded-full bg-violet-400/60" />
                成功 {timeRangeSuccessCount} · 失败 {timeRangeFailedCount}
              </div>
            </div>
          </div>

          {/* 执行队列卡片 */}
          <TaskQueueCard
            pendingCount={stats?.summary.pending_count ?? 0}
            runningCount={stats?.summary.running_count ?? 0}
            onStatusClick={(status) => {
              const params = new URLSearchParams();
              params.set("status", status);
              router.push(`/evidence?${params.toString()}`);
              setIsTaskListDrawerOpen(true);
            }}
          />
        </div>
      </section>

      <section className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-4 lg:items-stretch">
          <div className="lg:col-span-1">
            <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col h-[350px]">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-sm text-slate-500">成功 {successCount} 个 失败 {failedCount} 个</p>
                  <h3 className="text-lg font-semibold text-slate-900">
                    任务状态分布
                  </h3>
                </div>
              </div>
              <div className="mt-4 flex-1 min-h-[224px]">
                {distributionData && distributionData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={distributionData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={78}
                        innerRadius={0}
                        labelLine={true}
                        label={({ x, y, name, percentage }: any) => (
                          <text
                            x={x}
                            y={y}
                            fontSize="13"
                            fill="#475569"
                            textAnchor="middle"
                            dominantBaseline="central"
                          >
                            {`${name} (${percentage}%)`}
                          </text>
                        )}
                        onClick={(data) => {
                          const status = data.payload?.status;
                          if (status) {
                            const params = new URLSearchParams();
                            params.set("status", status.toLowerCase());
                            if (statsTimeRange.from && statsTimeRange.to) {
                              params.set("start_date", format(statsTimeRange.from, "yyyy-MM-dd"));
                              params.set("end_date", format(statsTimeRange.to, "yyyy-MM-dd"));
                            }
                            router.push(`/evidence?${params.toString()}`);
                          }
                        }}
                        cursor="pointer"
                        paddingAngle={2}
                        animationBegin={0}
                        animationDuration={400}
                      >
                        {distributionData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={entry.color ?? '#94a3b8'}
                            stroke="#fff"
                            strokeWidth={2}
                            style={{
                              filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))',
                              transition: 'opacity 0.2s'
                            }}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        content={({ payload }) => {
                          if (!payload?.[0]) return null;
                          const data = payload[0].payload;
                          return (
                            <div className="rounded-lg border border-sky-100 bg-white/95 backdrop-blur-sm p-3 shadow-lg">
                              <p className="font-semibold text-slate-900 mb-2">{data.name ?? '未知'}</p>
                              <div className="space-y-1">
                                <div className="flex items-center justify-between gap-4">
                                  <span className="text-sm text-slate-600">数量</span>
                                  <span className="font-semibold text-slate-900">{data.value ?? 0}</span>
                                </div>
                                <div className="flex items-center justify-between gap-4">
                                  <span className="text-sm text-slate-600">占比</span>
                                  <span className="font-semibold text-sky-600">{data.percentage ?? 0}%</span>
                                </div>
                              </div>
                              <p className="mt-2 text-xs text-sky-600">
                                点击查看详情 →
                              </p>
                            </div>
                          );
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-slate-400">
                    暂无状态数据
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-3 flex flex-col">
            <TaskListRecent
              tasks={stats?.recent_tasks || []}
              total={stats?.summary.total_tasks || 0}
              failureTypeLabel={failureTypeLabel}
              onTaskClick={setSelectedTask}
              onViewAll={() => {
                const params = new URLSearchParams();
                const queryString = params.toString();
                router.push(`/evidence${queryString ? `?${queryString}` : ""}`);
                setIsTaskListDrawerOpen(true);
              }}
            />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-4 lg:items-stretch">
          <div className="lg:col-span-1">
            <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col h-full">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-500">
                    Top 5（共 {stats.failure_summary?.total_failed || 0} 个失败）
                  </p>
                  <h3 className="text-lg font-semibold text-slate-900">
                    失败类型分布
                  </h3>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const params = new URLSearchParams();
                    params.set("status", "failed");
                    if (statsTimeRange.from && statsTimeRange.to) {
                      params.set("start_date", format(statsTimeRange.from, "yyyy-MM-dd"));
                      params.set("end_date", format(statsTimeRange.to, "yyyy-MM-dd"));
                    }
                    router.push(`/evidence?${params.toString()}`);
                    setIsTaskListDrawerOpen(true);
                  }}
                >
                  查看全部
                </Button>
              </div>
              <div className="mt-4 flex-1 min-h-[224px]">
                {stats.failure_type_distribution && stats.failure_type_distribution.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stats.failure_type_distribution} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis type="number" stroke="#94a3b8" />
                      <YAxis
                        type="category"
                        dataKey="label"
                        stroke="#94a3b8"
                        width={100}
                        tick={{ fontSize: 12 }}
                      />
                      <Tooltip
                        content={({ payload }) => {
                          if (!payload?.[0]) return null;
                          const data = payload[0].payload;
                          return (
                            <div className="rounded-lg border border-sky-100 bg-sky-50/90 backdrop-blur-sm p-3 shadow-md">
                              <p className="font-medium text-slate-900">{data.label}</p>
                              <p className="text-sm text-slate-500">
                                数量: <span className="font-semibold text-red-600">{data.count}</span>
                              </p>
                              <p className="text-xs text-slate-400">
                                占比: {data.percentage.toFixed(1)}%
                              </p>
                              <p className="mt-2 text-xs text-blue-600 hover:underline">
                                点击查看详情 →
                              </p>
                            </div>
                          );
                        }}
                      />
                      <Bar
                        dataKey="count"
                        radius={[0, 8, 8, 0]}
                        maxBarSize={30}
                        onClick={(data: any) => {
                          const failureType = data.payload?.type;
                          const params = new URLSearchParams();
                          params.set("status", "failed");
                          if (failureType && failureType !== 'others') {
                            params.set("failure_type", failureType);
                          }
                          if (statsTimeRange.from && statsTimeRange.to) {
                            params.set("start_date", format(statsTimeRange.from, "yyyy-MM-dd"));
                            params.set("end_date", format(statsTimeRange.to, "yyyy-MM-dd"));
                          }
                          router.push(`/evidence?${params.toString()}`);
                        }}
                        cursor="pointer"
                        label={{
                          position: 'right',
                          formatter: (_value: number, entry: any) => {
                            if (!entry || typeof entry.percentage === 'undefined') return '';
                            return `${entry.percentage.toFixed(1)}%`;
                          },
                          fontSize: 12,
                          fill: '#64748b'
                        }}
                      >
                        {stats.failure_type_distribution.map((_entry, index) => {
                          const colors = ['#f97316', '#fb923c', '#fbbf24', '#fcd34d', '#22d3ee', '#94a3b8'];
                          return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                        })}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-slate-400">
                    暂无失败数据
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-3">
            {stats?.daily_trend && stats.daily_trend.length > 0 ? (
              <DailyTrendChart
                dailyTrend={stats.daily_trend}
                days={5}
                onDateClick={handleDateClick}
              />
            ) : (
              <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col h-full">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      每日任务趋势
                    </h3>
                  </div>
                </div>
                <div className="mt-4 flex-1 flex items-center justify-center min-h-[224px]">
                  <div className="text-sm text-slate-400">暂无趋势数据</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 任务列表抽屉（暂时占位，后续实现） */}
      <Sheet
        open={isTaskListDrawerOpen}
        onOpenChange={(open) => {
          setIsTaskListDrawerOpen(open);
          if (!open) {
            const params = new URLSearchParams(searchParams.toString());
            params.delete("page");
            params.delete("status");
            params.delete("time_range");
            params.delete("failure_type");
            params.delete("q");
            const queryString = params.toString();
            router.push(`/evidence${queryString ? `?${queryString}` : ""}`);
          }
        }}
      >
        <SheetContent
          side="right"
          className="w-[95vw] sm:w-[93vw] lg:w-[90vw] overflow-y-auto p-6"
        >
          <SheetHeader className="mb-4">
            <SheetTitle>全部任务</SheetTitle>
            <SheetDescription>
              取证任务列表，支持筛选与检索
            </SheetDescription>
          </SheetHeader>
          <TaskListDrawer failureTypes={failureTypes} failureTypeLabel={failureTypeLabel} />
        </SheetContent>
      </Sheet>

      {/* 任务详情弹窗 */}
      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          failureTypeLabel={failureTypeLabel}
        />
      )}
    </DashboardShell>
  );
}
