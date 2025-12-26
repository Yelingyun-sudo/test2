"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { z } from "zod";
import {
  CartesianGrid,
  ComposedChart,
  Bar,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend
} from "recharts";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { DashboardShell } from "@/components/dashboard/shell";
import { cn, formatTokenCount } from "@/lib/utils";
import { toast } from "sonner";
import { clearLocalAuth, isJwtExpired, apiFetch } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";

const schema = z.object({
  username: z.string().min(1, "请输入用户名"),
  password: z.string().min(1, "请输入密码")
});

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

type FormValues = z.infer<typeof schema>;

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

export default function Page() {
  const router = useRouter();
  const [isAuthed, setIsAuthed] = useState(false);
  const [account, setAccount] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: ""
    }
  });

  useEffect(() => {
    setHydrated(true);
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("access_token");
    const savedAccount = localStorage.getItem("account_name");
    if (token && isJwtExpired(token)) {
      clearLocalAuth();
      toast.error("登录已过期，请重新登录");
      setIsAuthed(false);
      setAccount(null);
      return;
    }
    if (token) setIsAuthed(true);
    if (savedAccount) setAccount(savedAccount);
  }, []);

  // 获取统计数据
  useEffect(() => {
    if (!isAuthed) return;
    
    async function fetchStats() {
      setLoading(true);
      try {
        const statsRes = await apiFetch("/subscription/stats");
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
  }, [isAuthed]);

  const handleSubmit = async (values: FormValues) => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(values)
      });

      const data = (await res.json().catch(() => null)) as
        | { access_token?: string; detail?: string }
        | null;

      if (!res.ok) {
        const errorMessage = data?.detail ?? "登录失败，请检查账号密码。";
        throw new Error(errorMessage);
      }

      if (data?.access_token) {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("account_name", values.username);
        setAccount(values.username);
        setIsAuthed(true);
        toast.success("登录成功", { duration: 1000 });
        // 登录成功后跳转到订阅链接任务 Dashboard
        router.push("/subscription");
        return;
      }

      toast.success("登录成功", { duration: 1000 });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "登录失败，请稍后重试或联系管理员。";
      toast.error(message, { duration: 2000 });
    }
  };

  const handleLogout = () => {
    clearLocalAuth();
    setIsAuthed(false);
    setAccount(null);
    toast.success("已退出登录", { duration: 2000 });
  };

  // 水合完成前显示加载状态，避免登录框闪烁
  if (!hydrated) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
        </div>
      </main>
    );
  }

  if (isAuthed) {
    // 处理趋势图数据（只显示最近5天）
    const trendData = stats?.daily_trend
      ? stats.daily_trend.slice(-5).map((item) => ({
          date: new Date(item.date).toLocaleDateString("zh-CN", {
            month: "2-digit",
            day: "2-digit"
          }),
          total_count: item.total_count,
          success_count: item.success_count,
          failed_count: item.failed_count,
          success_rate: item.success_rate * 100 // 转换为百分比
        }))
      : [];

    return (
      <DashboardShell
        title="系统概览"
        description="系统概览与数据汇总"
        account={account ?? undefined}
        onLogout={handleLogout}
      >
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
          </div>
        ) : stats ? (
          <>
            {/* KPI 卡片 - Subscription 业务 */}
            <section className="mb-6">
              <h2 className="mb-4 text-lg font-semibold text-slate-900">订阅链接任务</h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {/* 总任务数 */}
                <div className="rounded-2xl border bg-gradient-to-br from-amber-500/10 to-amber-600/10 text-amber-700 border-amber-100 p-5 shadow-sm backdrop-blur">
                  <p className="text-sm text-slate-600">总任务数</p>
                  <div className="mt-2 flex items-baseline gap-3">
                    <div className="text-3xl font-semibold">
                      {stats.summary.total_tasks.toLocaleString()}
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-xs text-slate-600">成功率</span>
                      <span className="text-base text-slate-600">
                        {(stats.summary.success_rate * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                      <span className="h-2 w-2 rounded-full bg-amber-400/60" />
                      总计消耗 {formatTokenCount(stats.summary.total_tokens)} Token
                    </div>
                  </div>
                </div>

                {/* 今日已执行 */}
                <div className="rounded-2xl border bg-gradient-to-br from-sky-500/10 to-sky-600/10 text-sky-700 border-sky-100 p-5 shadow-sm backdrop-blur">
                  <p className="text-sm text-slate-600">今日已执行</p>
                  <div className="mt-2 flex items-baseline gap-3">
                    <div className="text-3xl font-semibold">
                      {stats.summary.today_success_count + stats.summary.today_failed_count}
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-xs text-slate-600">成功率</span>
                      <span className="text-base text-slate-600">
                        {(stats.summary.today_success_rate * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                      <span className="h-2 w-2 rounded-full bg-sky-400/60" />
                      待执行 {stats.summary.pending_count} · 执行中 {stats.summary.running_count}
                    </div>
                  </div>
                </div>

                {/* 今日成功 */}
                <div className="rounded-2xl border bg-gradient-to-br from-emerald-500/10 to-emerald-600/10 text-emerald-700 border-emerald-100 p-5 shadow-sm backdrop-blur">
                  <p className="text-sm text-slate-600">今日成功</p>
                  <div className="mt-2 flex items-baseline gap-3">
                    <div className="text-3xl font-semibold text-emerald-700">
                      {stats.summary.today_success_count}
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-xs text-slate-600">平均消耗</span>
                      <span className="text-base text-slate-600">
                        {formatTokenCount(stats.summary.today_avg_success_tokens)}
                      </span>
                      <span className="text-xs text-slate-600">Token</span>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                      <span className="h-2 w-2 rounded-full bg-emerald-400/60" />
                      平均耗时：{formatDurationSeconds(stats.summary.today_avg_success_duration_seconds)}
                    </div>
                  </div>
                </div>

                {/* 今日失败 */}
                <div className="rounded-2xl border bg-gradient-to-br from-rose-500/10 to-rose-600/10 text-rose-700 border-rose-100 p-5 shadow-sm backdrop-blur">
                  <p className="text-sm text-slate-600">今日失败</p>
                  <div className="mt-2 flex items-baseline gap-3">
                    <div className="text-3xl font-semibold text-rose-700">
                      {stats.summary.today_failed_count}
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-xs text-slate-600">平均消耗</span>
                      <span className="text-base text-slate-600">
                        {formatTokenCount(stats.summary.today_avg_failed_tokens)}
                      </span>
                      <span className="text-xs text-slate-600">Token</span>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-slate-600">
                      <span className="h-2 w-2 rounded-full bg-rose-400/60" />
                      平均耗时：{formatDurationSeconds(stats.summary.today_avg_failed_duration_seconds)}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* 趋势图区域 */}
            <section className="grid gap-6 lg:grid-cols-2">
              {/* Subscription 每日任务趋势 */}
              <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-slate-500">订阅链接任务 · 最近 5 天</p>
                    <h3 className="text-lg font-semibold text-slate-900">
                      每日任务趋势
                    </h3>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push("/subscription")}
                    className="group border-sky-200 text-sky-600 hover:bg-sky-200 hover:border-sky-300 hover:text-sky-800 transition-colors duration-200"
                  >
                    查看详情
                    <ArrowRight className="ml-1 h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                  </Button>
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

              {/* Evidence 每日趋势 - 预留位置 */}
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-slate-500">证据收集任务</p>
                    <h3 className="text-lg font-semibold text-slate-900">
                      每日任务趋势
                    </h3>
                  </div>
                </div>
                <div className="mt-4 flex h-72 items-center justify-center">
                  <div className="text-center">
                    <div className="mb-2 text-4xl">🚧</div>
                    <div className="text-sm font-medium text-slate-600">
                      敬请期待
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Evidence 业务趋势图即将上线
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="flex min-h-[400px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
            <div className="text-center">
              <div className="mb-2 text-4xl">📊</div>
              <div className="text-lg font-medium text-slate-700">
                暂无数据
              </div>
              <div className="mt-1 text-sm text-slate-500">
                请稍后再试
              </div>
            </div>
          </div>
        )}
      </DashboardShell>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
      <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-6 py-12 -mt-10">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white/90 shadow-xl backdrop-blur">
          <div className="border-b border-slate-100 px-8 py-6 text-center">
            <h2 className="mt-1 text-2xl font-semibold text-slate-900">Website Analytics 控制台</h2>
          </div>

          <div className="px-8 py-8">
            <Form {...form}>
              <form
                className="space-y-6"
                onSubmit={form.handleSubmit(handleSubmit)}
                method="post"
                noValidate
              >
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem className="space-y-2">
                      <div className="flex items-center gap-3">
                        <FormLabel className="w-14 shrink-0 text-left">账号</FormLabel>
                        <FormControl className="flex-1">
                          <Input
                            placeholder="请输入账号"
                            autoComplete="username"
                            {...field}
                          />
                        </FormControl>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem className="space-y-2">
                      <div className="flex items-center gap-3">
                        <FormLabel className="w-14 shrink-0 text-left">密码</FormLabel>
                        <FormControl className="flex-1">
                          <Input
                            type="password"
                            placeholder="请输入密码"
                            autoComplete="current-password"
                            {...field}
                          />
                        </FormControl>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  className={cn(
                    "inline-flex w-full items-center justify-center gap-2",
                    "bg-gradient-to-r from-sky-600 to-cyan-500 text-white shadow-lg shadow-sky-200",
                    "hover:from-sky-700 hover:to-cyan-600"
                  )}
                  disabled={!hydrated || form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting ? (
                    <span className="flex items-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                      登录中...
                    </span>
                  ) : (
                    <>
                      登录
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>
            </Form>
          </div>
        </div>
      </div>
    </main>
  );
}
