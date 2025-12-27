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
import { TaskListDrawer } from "@/components/subscription/task-list-drawer";
import { TaskDetailModal } from "@/components/subscription/task-detail-modal";
import { TaskQueueCard } from "@/components/subscription/task-queue-card";
import { TaskListRecent } from "@/components/subscription/task-list-recent";
import { TimeRangeSelector } from "@/components/subscription/time-range-selector";
import { DailyTrendChart } from "./daily-trend-chart";
import { DashboardShell } from "./shell";
import { apiFetch } from "@/lib/api";
import { formatDurationSeconds } from "@/lib/datetime";
import { formatTokenCount } from "@/lib/utils";
import { toast } from "sonner";
import type { StatsResponse } from "@/lib/types";
import { STATUS_LABELS, STATUS_COLORS_ENHANCED, type TaskStatus, type FailureTypeItem, type FailureTypesResponse } from "@/types/common";
import type { SubscriptionItem, SubscriptionListResponse } from "@/types/subscription";

type DashboardProps = {
  onLogout: () => void;
  account?: string;
};

export function SubscriptionDashboard({ onLogout, account }: DashboardProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // 下半部分独立的时间范围状态
  const [statsTimeRange, setStatsTimeRange] = useState("today");
  
  // 统计数据状态
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  
  // 最新任务列表状态（不受时间筛选影响）
  const [recentTasks, setRecentTasks] = useState<SubscriptionItem[]>([]);
  const [totalRecentTasks, setTotalRecentTasks] = useState<number>(0);
  
  // UI 状态
  const [isTaskListDrawerOpen, setIsTaskListDrawerOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<SubscriptionItem | null>(null);
  const [failureTypes, setFailureTypes] = useState<FailureTypeItem[]>([]);

  // 检查 URL 参数，如果有任务查询相关参数，自动打开抽屉
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

  // 下半部分统计数据获取（受 statsTimeRange 控制）
  useEffect(() => {
    async function fetchStats() {
      try {
        const params = new URLSearchParams();
        if (statsTimeRange && statsTimeRange !== "ALL") {
          params.set("time_range", statsTimeRange);
        }
        const url = `/subscription/stats${params.toString() ? `?${params.toString()}` : ""}`;
        
        const statsRes = await apiFetch(url);
        const statsData = await statsRes.json();
        setStats(statsData);
      } catch (error) {
        toast.error("加载统计数据失败");
        console.error(error);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, [statsTimeRange]);

  // 获取失败类型列表
  useEffect(() => {
    const fetchFailureTypes = async () => {
      try {
        const res = await apiFetch("/subscription/failure-types");
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

  // 获取最新任务列表（与 TaskListDrawer 第 1 页前 5 条保持一致）
  useEffect(() => {
    async function fetchRecentTasks() {
      try {
        // 获取所有任务（不筛选状态和时间），第 1 页，取 5 条
        // 与 TaskListDrawer 默认行为一致：status=ALL, timeRange=ALL, page=1
        const params = new URLSearchParams({
          page: "1",
          page_size: "5"
        });
        const url = `/subscription/list?${params.toString()}`;
        const recentRes = await apiFetch(url);
        if (!recentRes.ok) {
          throw new Error("获取任务列表失败");
        }
        const recentData = (await recentRes.json()) as SubscriptionListResponse;
        setRecentTasks(recentData.items || []);
        setTotalRecentTasks(recentData.total ?? 0);
      } catch (error) {
        console.error("加载最新任务失败", error);
      }
    }
    fetchRecentTasks();
  }, []);

  // 从 API 获取的失败类型构建标签映射（必须在所有条件返回之前）
  const failureTypeLabel: Record<string, string> = useMemo(() => {
    return failureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);
  }, [failureTypes]);

  // 根据时间范围生成 KPI 卡片标题前缀
  const getTimeRangeLabel = (range: string): string => {
    switch (range) {
      case "today":
        return "今日";
      case "yesterday":
        return "昨日";
      case "3d":
        return "近3天";
      case "7d":
        return "近7天";
      case "30d":
        return "近30天";
      case "ALL":
        return "总计";
      default:
        return "今日";
    }
  };

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

  // 过滤掉"待执行"和"执行中"状态，只保留"成功"和"失败"
  const completedStatusDistribution = status_distribution.filter(
    (item) => item.status === "SUCCESS" || item.status === "FAILED"
  );
  
  // 只计算成功和失败的总数
  const totalCompletedCount = completedStatusDistribution.reduce((sum, item) => sum + item.count, 0);
  const distributionData = completedStatusDistribution.map((item) => ({
    name: STATUS_LABELS[item.status as TaskStatus] || item.status,
    value: item.count,
    color: STATUS_COLORS_ENHANCED[item.status as TaskStatus] || "#94a3b8",
    percentage: totalCompletedCount > 0 ? ((item.count / totalCompletedCount) * 100).toFixed(1) : 0,
    status: item.status  // 保存原始状态值用于路由跳转
  }));

  // 获取成功和失败的数量
  const successCount = distributionData.find(item => item.status === "SUCCESS")?.value || 0;
  const failedCount = distributionData.find(item => item.status === "FAILED")?.value || 0;

  // 计算已执行任务的平均耗时（加权平均）
  const totalExecuted = summary.today_success_count + summary.today_failed_count;
  const avgDurationSeconds = totalExecuted > 0
    ? (summary.today_success_count * summary.today_avg_success_duration_seconds +
       summary.today_failed_count * summary.today_avg_failed_duration_seconds) / totalExecuted
    : null;

  // 根据时间范围计算成功率（使用 today_success_count 和 today_failed_count）
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
      {/* 上半部分：数据统计区域 */}
      <section className="space-y-4">
        {/* 时间选择器 */}
        <TimeRangeSelector 
          value={statsTimeRange}
          onChange={setStatsTimeRange}
        />
        
        {/* KPI 卡片 */}
        <div className="grid gap-4 md:grid-cols-5">
          {/* 已执行 */}
          <div className="rounded-2xl border bg-gradient-to-br from-sky-500/10 to-sky-600/10 text-sky-700 border-sky-100 p-5 shadow-sm backdrop-blur">
            <p className="text-sm text-slate-600">{timeRangeLabel}已执行</p>
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
            onStatusClick={(status) => {
              const params = new URLSearchParams();
              params.set("status", status);
              router.push(`/subscription?${params.toString()}`);
              setIsTaskListDrawerOpen(true);
            }}
          />
        </div>
        
      </section>

      {/* 下半部分：任务列表和图表区域 */}
      <section className="space-y-4">
        {/* 第一行：任务状态分布 + 最新任务列表 */}
        <div className="grid gap-4 lg:grid-cols-4 lg:items-stretch">
          {/* 左侧1/4：任务状态分布图 */}
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
                            if (statsTimeRange && statsTimeRange !== "ALL") {
                              params.set("time_range", statsTimeRange);
                            }
                            router.push(`/subscription?${params.toString()}`);
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

          {/* 右侧3/4：最新任务列表 */}
          <div className="lg:col-span-3 flex flex-col">
            <TaskListRecent
              tasks={recentTasks}
              total={totalRecentTasks}
              failureTypeLabel={failureTypeLabel}
              onTaskClick={setSelectedTask}
              onViewAll={() => {
                const params = new URLSearchParams();
                const queryString = params.toString();
                router.push(`/subscription${queryString ? `?${queryString}` : ""}`);
                setIsTaskListDrawerOpen(true);
              }}
            />
          </div>
        </div>

        {/* 第二行：失败类型分布 + 每日任务趋势 */}
        <div className="grid gap-4 lg:grid-cols-4 lg:items-stretch">
          {/* 左侧1/4：失败类型分布图 */}
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
                    if (statsTimeRange && statsTimeRange !== "ALL") {
                      params.set("time_range", statsTimeRange);
                    }
                    router.push(`/subscription?${params.toString()}`);
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
                          if (statsTimeRange && statsTimeRange !== "ALL") {
                            params.set("time_range", statsTimeRange);
                          }
                          router.push(`/subscription?${params.toString()}`);
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

          {/* 右侧3/4：每日任务趋势 */}
          <div className="lg:col-span-3">
            {stats?.daily_trend && stats.daily_trend.length > 0 ? (
              <DailyTrendChart
                dailyTrend={stats.daily_trend}
                days={5}
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

      {/* 任务列表抽屉 */}
      <Sheet 
        open={isTaskListDrawerOpen} 
        onOpenChange={(open) => {
          setIsTaskListDrawerOpen(open);
          // 当抽屉关闭时，清理筛选相关的 URL 参数
          if (!open) {
            const params = new URLSearchParams(searchParams.toString());
            // 清理抽屉筛选参数
            params.delete("page");
            params.delete("status");
            params.delete("time_range");
            params.delete("failure_type");
            params.delete("q");
            // 保留 time_range（页面级时间范围选择器）
            const queryString = params.toString();
            router.push(`/subscription${queryString ? `?${queryString}` : ""}`);
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
              订阅链接任务列表，支持筛选与检索
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

