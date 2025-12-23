"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CartesianGrid,
  Cell,
  ComposedChart,
  Bar,
  BarChart,
  Line,
  PieChart,
  Pie,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend
} from "recharts";

import { Button } from "@/components/ui/button";
import { DashboardShell } from "./shell";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { cn, formatTokenCount } from "@/lib/utils";
import { toast } from "sonner";
import type { StatsResponse } from "@/lib/types";

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

// 状态映射
const statusLabel: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  success: "成功",
  failed: "失败"
};

const statusStyles: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  running: "bg-yellow-100 text-yellow-700",
  success: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700"
};

const statusColor: Record<string, string> = {
  pending: "#94a3b8",
  running: "#facc15",
  success: "#22c55e",
  failed: "#ef4444"
};

export function RealDashboard({ onLogout, account }: DashboardProps) {
  const router = useRouter();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // 数据获取逻辑（仅在页面加载时执行一次）
  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await apiFetch("/subscription/stats");
        const data = await res.json();
        setStats(data);
      } catch (error) {
        toast.error("加载统计数据失败");
        console.error(error);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

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

  const { summary, daily_trend, status_distribution, recent_tasks } = stats;

  // 处理图表数据（只显示最近5天）
  const trendData = daily_trend.slice(-5).map((item) => ({
    date: new Date(item.date).toLocaleDateString("zh-CN", {
      month: "2-digit",
      day: "2-digit"
    }),
    total_count: item.total_count,
    success_count: item.success_count,
    failed_count: item.failed_count,
    success_rate: item.success_rate * 100 // 转换为百分比
  }));

  const totalStatusCount = status_distribution.reduce((sum, item) => sum + item.count, 0);
  const distributionData = status_distribution.map((item) => ({
    name: statusLabel[item.status] || item.status,
    value: item.count,
    color: statusColor[item.status] || "#94a3b8",
    percentage: totalStatusCount > 0 ? ((item.count / totalStatusCount) * 100).toFixed(1) : 0,
    status: item.status  // 保存原始状态值用于路由跳转
  }));

  return (
    <DashboardShell
      account={account}
      onLogout={onLogout}
    >
      {/* KPI 卡片 */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {/* 总任务数 */}
        <div className="rounded-2xl border bg-gradient-to-br from-amber-500/10 to-amber-600/10 text-amber-700 border-amber-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">总任务数</p>
          <div className="mt-2 flex items-baseline gap-3">
            <div className="text-3xl font-semibold">
              {summary.total_tasks.toLocaleString()}
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-base text-slate-600">
                {formatTokenCount(summary.total_tokens)}
              </span>
              <span className="text-xs text-slate-600">token</span>
            </div>
          </div>
          <div className="mt-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
              <span className="h-2 w-2 rounded-full bg-amber-400/60" />
              平均 {daily_trend.length > 0 ? Math.round(summary.total_tasks / daily_trend.length) : 0} 个/天
            </div>
          </div>
        </div>

        {/* 今日已执行 */}
        <div className="rounded-2xl border bg-gradient-to-br from-sky-500/10 to-sky-600/10 text-sky-700 border-sky-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">今日已执行</p>
          <div className="mt-2 flex items-baseline gap-3">
            <div className="text-3xl font-semibold">
              {summary.today_success_count + summary.today_failed_count}
            </div>
            <div className="flex items-baseline gap-1">
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

        {/* 今日成功任务 */}
        <div className="rounded-2xl border bg-gradient-to-br from-emerald-500/10 to-emerald-600/10 text-emerald-700 border-emerald-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">今日成功任务</p>
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

        {/* 今日失败任务 */}
        <div className="rounded-2xl border bg-gradient-to-br from-rose-500/10 to-rose-600/10 text-rose-700 border-rose-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">今日失败任务</p>
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

        {/* 今日成功率 */}
        <div className="rounded-2xl border bg-gradient-to-br from-violet-500/10 to-indigo-600/10 text-indigo-700 border-indigo-100 p-5 shadow-sm backdrop-blur">
          <p className="text-sm text-slate-600">今日成功率</p>
          <div className="mt-2 text-3xl font-semibold">
            {(summary.today_success_rate * 100).toFixed(1)}%
          </div>
          <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
            <span className="h-2 w-2 rounded-full bg-indigo-400/60" />
            成功 {summary.today_success_count} · 失败 {summary.today_failed_count}
          </div>
        </div>
      </section>

      {/* 图表区域 */}
      <section className="grid gap-6 lg:grid-cols-3">
        {/* 每日任务趋势图 - 2/3 宽度 */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-500">最近 5 天</p>
              <h3 className="text-lg font-semibold text-slate-900">
                每日任务趋势
              </h3>
            </div>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis yAxisId="left" stroke="#94a3b8" />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke="#94a3b8"
                  unit="%"
                  domain={[0, 100]}
                />
                <Tooltip
                  content={({ payload, label }) => {
                    if (!payload || payload.length === 0) return null;
                    return (
                      <div className="rounded-lg border border-sky-100 bg-sky-50/90 backdrop-blur-sm p-3 shadow-md">
                        <p className="font-medium text-slate-900 mb-2">{label}</p>
                        <div className="space-y-1">
                          {payload.map((entry, index) => (
                            <div key={index} className="flex items-center justify-between gap-4">
                              <div className="flex items-center gap-2">
                                <span
                                  className="inline-block h-3 w-3 rounded-sm"
                                  style={{ backgroundColor: entry.color ?? '#94a3b8' }}
                                />
                                <span className="text-xs text-slate-600">{entry.name ?? '未知'}</span>
                              </div>
                              <span className="text-sm font-semibold text-slate-900">
                                {entry.name === "成功率"
                                  ? `${Number(entry.value ?? 0).toFixed(1)}%`
                                  : entry.value ?? 0}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  }}
                />
                <Legend
                  formatter={(value) => <span style={{ color: '#475569', fontSize: '12px', fontWeight: 500 }}>{value}</span>}
                />
                <Bar
                  yAxisId="right"
                  dataKey="success_rate"
                  name="成功率"
                  fill="#c7d2fe"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={60}
                  legendType="square"
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="total_count"
                  name="总任务数"
                  stroke="#0ea5e9"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#0ea5e9" }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="success_count"
                  name="成功任务数"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#22c55e" }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="failed_count"
                  name="失败任务数"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#ef4444" }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 任务状态分布图 - 1/3 宽度 */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-1">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-500">状态统计</p>
              <h3 className="text-lg font-semibold text-slate-900">
                任务状态分布
              </h3>
            </div>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distributionData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={(entry) => `${entry.name ?? '未知'} (${entry.percentage ?? 0}%)`}
                  onClick={(data) => {
                    // 点击饼图扇区跳转到订阅列表，自动筛选该状态
                    const status = data.payload?.status;
                    if (status) {
                      router.push(`/subscription?status=${encodeURIComponent(status)}`);
                    }
                  }}
                  cursor="pointer"
                >
                  {distributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color ?? '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.[0]) return null;
                    const data = payload[0].payload;
                    return (
                      <div className="rounded-lg border border-sky-100 bg-sky-50/90 backdrop-blur-sm p-3 shadow-md">
                        <p className="font-medium text-slate-900">{data.name ?? '未知'}</p>
                        <p className="text-sm text-slate-500">
                          数量: <span className="font-semibold text-sky-600">{data.value ?? 0}</span>
                        </p>
                        <p className="text-xs text-slate-400">
                          占比: {data.percentage ?? 0}%
                        </p>
                        <p className="mt-2 text-xs text-blue-600 hover:underline">
                          点击查看详情 →
                        </p>
                      </div>
                    );
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 最近任务列表 - 2/3 宽度 */}
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-2">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-slate-500">最新 5 个</p>
            <h3 className="text-lg font-semibold text-slate-900">
              最近任务列表
            </h3>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse">
            <colgroup>
              <col className="w-[5%]" />
              <col className="w-[18%]" />
              <col className="w-[12%]" />
              <col className="w-[30%]" />
              <col className="w-[16%]" />
              <col className="w-[19%]" />
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
              {recent_tasks.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="p-4 text-center text-sm text-slate-500"
                  >
                    暂无任务记录
                  </td>
                </tr>
              ) : (
                recent_tasks.map((task) => (
                  <tr
                    key={task.id}
                    className="border-b border-slate-100 hover:bg-slate-50"
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
                          "inline-block rounded-full px-2 py-1 text-xs font-medium",
                          statusStyles[task.status] || "bg-slate-100 text-slate-700"
                        )}
                      >
                        {statusLabel[task.status] || task.status}
                      </span>
                    </td>
                    <td className="p-2 text-sm text-slate-700">
                      {task.executed_at ? formatDateTime(task.executed_at) : "-"}
                    </td>
                    <td className="p-2 text-sm text-slate-700">
                      {task.status === "running" || task.status === "pending"
                        ? "-"
                        : formatDurationSeconds(task.duration_seconds)}
                    </td>
                    <td className="p-2 text-sm text-slate-700">
                      <div className="max-w-[200px] truncate" title={task.result || ""}>
                        {task.result || "-"}
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
              onClick={() => router.push('/subscription?status=failed')}
            >
              查看全部
            </Button>
          </div>
          <div className="mt-4 h-72">
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
                    onClick={(data) => {
                      // 点击跳转到订阅列表，自动筛选该失败类型
                      const failureType = data.payload?.type;
                      if (failureType && failureType !== 'others') {
                        router.push(`/subscription?status=failed&failure_type=${encodeURIComponent(failureType)}`);
                      } else if (failureType === 'others') {
                        router.push('/subscription?status=failed');
                      }
                    }}
                    cursor="pointer"
                    label={{
                      position: 'right',
                      formatter: (value: number, entry: any) => {
                        if (!entry || typeof entry.percentage === 'undefined') return '';
                        return `${entry.percentage.toFixed(1)}%`;
                      },
                      fontSize: 12,
                      fill: '#64748b'
                    }}
                  >
                    {stats.failure_type_distribution.map((entry, index) => {
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
    </DashboardShell>
  );
}
