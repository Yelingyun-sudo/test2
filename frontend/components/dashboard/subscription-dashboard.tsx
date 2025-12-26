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
import { ArrowRight, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { TasksDrawer } from "@/components/subscription/tasks-drawer";
import { TaskDetailModal } from "@/components/subscription/task-detail-modal";
import { DashboardShell } from "./shell";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { cn, formatTokenCount } from "@/lib/utils";
import { toast } from "sonner";
import type { StatsResponse } from "@/lib/types";
import { STATUS_LABELS, STATUS_STYLES, STATUS_COLORS_ENHANCED, type TaskStatus, type FailureTypeItem, type FailureTypesResponse } from "@/types/common";
import type { SubscriptionItem, SubscriptionListResponse } from "@/types/subscription";

type DashboardProps = {
  onLogout: () => void;
  account?: string;
};

// 格式化时长
function formatDurationSeconds(value?: number | null): string {
  if (value == null || isNaN(value)) return "-";
  const totalSeconds = Math.max(0, Math.floor(value));
  if (totalSeconds < 60) return `${totalSeconds}秒`;

  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (totalSeconds < 3600) return `${minutes}分${seconds}秒`;
  if (totalSeconds < 86_400)
    return `${hours}小时${minutes}分${seconds}秒`;
  return `${days}天${hours}小时${minutes}分${seconds}秒`;
}


export function SubscriptionDashboard({ onLogout, account }: DashboardProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isTasksDrawerOpen, setIsTasksDrawerOpen] = useState(false);

  // 最新任务完整数据（用于显示详情）
  const [recentTasks, setRecentTasks] = useState<SubscriptionItem[]>([]);
  
  // 总任务数
  const [totalTasks, setTotalTasks] = useState<number>(0);

  // 任务详情弹窗相关状态
  const [selectedTask, setSelectedTask] = useState<SubscriptionItem | null>(null);

  // 响应式：判断是否为桌面端
  const [isDesktop, setIsDesktop] = useState(true);

  // 失败类型列表
  const [failureTypes, setFailureTypes] = useState<FailureTypeItem[]>([]);

  // 从 URL 读取时间范围，默认为 "today"（由全局 header 控制）
  const timeRange = searchParams.get("time_range") || "today";

  // 检查 URL 参数，如果有任务查询相关参数，自动打开抽屉
  useEffect(() => {
    const hasQueryParams = 
      searchParams.get("page") ||
      searchParams.get("status") ||
      searchParams.get("executed_within") ||
      searchParams.get("failure_type") ||
      searchParams.get("q");
    
    if (hasQueryParams) {
      setIsTasksDrawerOpen(true);
    }
  }, [searchParams]);

  // 响应式检测：桌面端 vs 移动端
  useEffect(() => {
    const checkIsDesktop = () => {
      setIsDesktop(window.innerWidth >= 1024); // lg breakpoint
    };
    
    checkIsDesktop();
    window.addEventListener("resize", checkIsDesktop);
    return () => window.removeEventListener("resize", checkIsDesktop);
  }, []);

  // 数据获取逻辑（根据时间范围获取统计数据）
  useEffect(() => {
    async function fetchStats() {
      try {
        // 构建查询参数
        const params = new URLSearchParams();
        if (timeRange && timeRange !== "ALL") {
          params.set("executed_within", timeRange);
        }
        const url = `/subscription/stats${params.toString() ? `?${params.toString()}` : ""}`;
        
        // 获取统计数据
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
  }, [timeRange]);

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

  // 根据响应式状态和时间范围获取最新任务列表
  useEffect(() => {
    async function fetchRecentTasks() {
      try {
        // 桌面端显示 13 条，移动端显示 8 条
        const pageSize = isDesktop ? 13 : 8;
        // 构建查询参数，包含时间范围
        const params = new URLSearchParams({
          page: "1",
          page_size: String(pageSize)
        });
        if (timeRange && timeRange !== "ALL") {
          params.set("executed_within", timeRange);
        }
        const recentRes = await apiFetch(`/subscription/list?${params.toString()}`);
        if (!recentRes.ok) {
          throw new Error("获取任务列表失败");
        }
        const recentData = (await recentRes.json()) as SubscriptionListResponse;
        setRecentTasks(recentData.items || []);
        setTotalTasks(recentData.total ?? 0);
      } catch (error) {
        console.error("加载最新任务失败", error);
      }
    }
    fetchRecentTasks();
  }, [isDesktop, timeRange]);

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

  const timeRangeLabel = getTimeRangeLabel(timeRange);

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

  const totalStatusCount = status_distribution.reduce((sum, item) => sum + item.count, 0);
  const distributionData = status_distribution.map((item) => ({
    name: STATUS_LABELS[item.status as TaskStatus] || item.status,
    value: item.count,
    color: STATUS_COLORS_ENHANCED[item.status as TaskStatus] || "#94a3b8",
    percentage: totalStatusCount > 0 ? ((item.count / totalStatusCount) * 100).toFixed(1) : 0,
    status: item.status  // 保存原始状态值用于路由跳转
  }));

  return (
    <DashboardShell
      account={account}
      onLogout={onLogout}
    >
      {/* KPI 卡片 */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* 今日已执行 */}
        <div className="rounded-2xl border bg-gradient-to-br from-sky-500/10 to-sky-600/10 text-sky-700 border-sky-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">{timeRangeLabel}已执行</p>
          <div className="mt-2 flex items-baseline gap-3">
            <div className="text-3xl font-semibold">
              {summary.today_success_count + summary.today_failed_count}
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xs text-slate-600">总计消耗</span>
              <span className="text-base text-slate-600">
                {formatTokenCount(summary.today_tokens)}
              </span>
              <span className="text-xs text-slate-600">token</span>
            </div>
          </div>
          <div className="mt-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
              <span className="h-2 w-2 rounded-full bg-sky-400/60" />
              待执行 {summary.pending_count} · 执行中 {summary.running_count}
            </div>
          </div>
        </div>

        {/* 今日成功 */}
        <div className="rounded-2xl border bg-gradient-to-br from-emerald-500/10 to-emerald-600/10 text-emerald-700 border-emerald-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">{timeRangeLabel}成功</p>
          <div className="mt-2 flex items-baseline gap-3">
            <div className="text-3xl font-semibold text-emerald-700">
              {summary.today_success_count}
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xs text-slate-600">平均消耗</span>
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

        {/* 今日失败 */}
        <div className="rounded-2xl border bg-gradient-to-br from-rose-500/10 to-rose-600/10 text-rose-700 border-rose-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">{timeRangeLabel}失败</p>
          <div className="mt-2 flex items-baseline gap-3">
            <div className="text-3xl font-semibold text-rose-700">
              {summary.today_failed_count}
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xs text-slate-600">平均消耗</span>
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

        {/* 今日成功率 */}
        <div className="rounded-2xl border bg-gradient-to-br from-violet-500/10 to-violet-600/10 text-violet-800 border-violet-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">{timeRangeLabel}成功率</p>
          <div className="mt-2">
            <div className="text-3xl font-semibold text-violet-800">
              {(summary.today_success_rate * 100).toFixed(1)}%
            </div>
          </div>
          <div className="mt-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
              <span className="h-2 w-2 rounded-full bg-violet-400/60" />
              成功 {summary.today_success_count} · 失败 {summary.today_failed_count}
            </div>
          </div>
        </div>
      </section>

      {/* 图表区域 */}
      <section className="grid gap-6 lg:grid-cols-4 lg:grid-rows-2">
        {/* 任务状态分布图 - 1/3 宽度 */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-1">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-sm text-slate-500">状态统计（共 {status_distribution.length} 种状态）</p>
              <h3 className="text-lg font-semibold text-slate-900">
                任务状态分布
              </h3>
            </div>
          </div>
          <div className="mt-4 h-56">
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
                      // 点击饼图扇区跳转到订阅列表，自动筛选该状态
                      const status = data.payload?.status;
                      if (status) {
                        // 将当前页面的时间范围参数传递给抽屉
                        const params = new URLSearchParams();
                        params.set("status", status.toLowerCase());
                        if (timeRange) {
                          params.set("time_range", timeRange);
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

        {/* 最新任务列表 - 3/4 宽度（1:3 比例），占满两行 */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-3 lg:row-span-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold text-slate-900">
              任务列表
            </h3>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                {totalTasks} 条
              </span>
              <span className="text-xs text-slate-500">
                显示前 {isDesktop ? 13 : 8} 条
              </span>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              // 将当前页面的时间范围参数传递给抽屉
              const params = new URLSearchParams();
              if (timeRange) {
                params.set("time_range", timeRange);
              }
              const queryString = params.toString();
              router.push(`/subscription${queryString ? `?${queryString}` : ""}`);
              setIsTasksDrawerOpen(true);
            }}
            className="group border-sky-200 text-sky-600 hover:bg-sky-200 hover:border-sky-300 hover:text-sky-800 transition-colors duration-200"
          >
            显示全部
            <ArrowRight className="ml-1 h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          </Button>
        </div>
        <div className="mt-4 max-h-[600px] overflow-y-auto overflow-x-auto">
          <table className="w-full border-collapse">
            <colgroup>
              <col className="w-[5%]" />
              <col className="w-[14%]" />
              <col className="w-[12%]" />
              <col className="w-[22%]" />
              <col className="w-[12%]" />
              <col className="w-[35%]" />
            </colgroup>
            <thead>
              <tr className="border-b border-slate-200">
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
                  执行时间
                </th>
                <th className="p-2 text-left text-xs font-medium text-slate-500">
                  耗时
                </th>
                <th className="p-2 text-left text-xs font-medium text-slate-500">
                  结果
                </th>
              </tr>
            </thead>
            <tbody>
              {recentTasks.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="p-4 text-center text-sm text-slate-500"
                  >
                    暂无任务记录
                  </td>
                </tr>
              ) : (
                recentTasks.map((task) => (
                  <tr
                    key={task.id}
                    className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => setSelectedTask(task)}
                  >
                    <td className="p-2 text-sm text-slate-700">{task.id}</td>
                    <td className="p-2 text-sm text-slate-700">
                      <div className="max-w-[160px] truncate" title={task.url}>
                        {task.url}
                      </div>
                    </td>
                    <td className="p-2">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
                          STATUS_STYLES[task.status as TaskStatus] || "bg-slate-100 text-slate-600 border border-slate-200"
                        )}
                      >
                        {task.status === "RUNNING" && (
                          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                        )}
                        {STATUS_LABELS[task.status as TaskStatus] || task.status}
                      </span>
                    </td>
                    <td className="p-2 text-sm text-slate-700">
                      {task.executed_at ? formatDateTime(task.executed_at) : "-"}
                    </td>
                    <td className="p-2 text-sm text-slate-700">
                      {task.status === "RUNNING" || task.status === "PENDING"
                        ? "-"
                        : formatDurationSeconds(task.duration_seconds)}
                    </td>
                    <td className="p-2 text-sm text-slate-700">
                      <div className="flex items-center gap-2 min-w-0 max-w-[270px]">
                        {task.status === "FAILED" && task.failure_type && (
                          <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10 flex-shrink-0">
                            {failureTypeLabel[task.failure_type] || task.failure_type}
                          </span>
                        )}
                        <span className="truncate" title={task.result || ""}>
                          {task.result || "-"}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        </div>

        {/* 失败类型分布图 - 1/3 宽度 - 饼图 */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-1">
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
                // 将当前页面的时间范围参数传递给抽屉
                const params = new URLSearchParams();
                params.set("status", "failed");
                if (timeRange) {
                  params.set("time_range", timeRange);
                }
                router.push(`/subscription?${params.toString()}`);
                setIsTasksDrawerOpen(true);
              }}
            >
              查看全部
            </Button>
          </div>
          <div className="mt-4 h-56">
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
                      // 点击跳转到订阅列表，自动筛选该失败类型
                      const failureType = data.payload?.type;
                      // 将当前页面的时间范围参数传递给抽屉
                      const params = new URLSearchParams();
                      params.set("status", "failed");
                      if (failureType && failureType !== 'others') {
                        params.set("failure_type", failureType);
                      }
                      if (timeRange) {
                        params.set("time_range", timeRange);
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
                      // 渐变色谱配色：橙 → 琥珀 → 青 → 灰
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
      </section>

      {/* 任务列表抽屉 */}
      <Sheet 
        open={isTasksDrawerOpen} 
        onOpenChange={(open) => {
          setIsTasksDrawerOpen(open);
          // 当抽屉关闭时，清理筛选相关的 URL 参数
          if (!open) {
            const params = new URLSearchParams(searchParams.toString());
            // 清理抽屉筛选参数
            params.delete("page");
            params.delete("status");
            params.delete("executed_within");
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
          <TasksDrawer />
        </SheetContent>
      </Sheet>

      {/* 任务详情弹窗 */}
      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </DashboardShell>
  );
}

