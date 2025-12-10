"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowRight,
  LineChart,
  ShieldCheck,
  Sparkles,
  UserRound
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart as ReLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { DashboardShell } from "@/components/dashboard/shell";
import { dashboardNavItems } from "@/components/dashboard/nav";
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
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const schema = z.object({
  username: z.string().min(1, "请输入用户名"),
  password: z.string().min(1, "请输入密码")
});

const features = [
  {
    title: "安全合规",
    desc: "数据按角色隔离，支持精细化审计。",
    icon: ShieldCheck
  },
  {
    title: "实时洞察",
    desc: "秒级看板刷新，异常自动提醒。",
    icon: LineChart
  },
  {
    title: "智能助理",
    desc: "用自然语言提问，快速生成报告。",
    icon: Sparkles
  },
  {
    title: "团队协作",
    desc: "多成员并行操作，记录可追溯。",
    icon: UserRound
  }
];

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

type FormValues = z.infer<typeof schema>;

const visitsTrend = [
  { name: "09:00", uv: 1280, pv: 860 },
  { name: "10:00", uv: 1420, pv: 920 },
  { name: "11:00", uv: 1380, pv: 880 },
  { name: "12:00", uv: 1550, pv: 1030 },
  { name: "13:00", uv: 1670, pv: 1190 },
  { name: "14:00", uv: 1760, pv: 1250 },
  { name: "15:00", uv: 1820, pv: 1320 }
];

const channelShare = [
  { name: "广告投放", value: 38, color: "#22c55e" },
  { name: "自然搜索", value: 27, color: "#0ea5e9" },
  { name: "社交分享", value: 21, color: "#6366f1" },
  { name: "直接访问", value: 14, color: "#f97316" }
];

const retentionData = [
  { day: "D0", rate: 100 },
  { day: "D1", rate: 62 },
  { day: "D3", rate: 48 },
  { day: "D7", rate: 35 },
  { day: "D14", rate: 28 },
  { day: "D30", rate: 18 }
];

export default function Page() {
  const [isAuthed, setIsAuthed] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: ""
    }
  });

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    if (token) {
      setIsAuthed(true);
    }
  }, []);

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
        setIsAuthed(true);
      }

      toast.success("登录成功", {
        description: "已通过 admin/admin 静态校验，后续可接入真实鉴权。"
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "登录失败，请稍后重试或联系管理员。";
      toast.error(message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    setIsAuthed(false);
    toast.success("已退出登录");
  };

  if (isAuthed) {
    return (
      <Dashboard onLogout={handleLogout} />
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
      <div className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-12">
        <div className="grid w-full gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-800 via-sky-600 to-cyan-500 p-[1px] shadow-2xl">
            <div className="grainy relative h-full w-full rounded-[calc(1.5rem-1px)] bg-gradient-to-br from-sky-950/50 via-sky-900/40 to-sky-800/50 px-8 py-10 text-white">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.12),transparent_32%),radial-gradient(circle_at_80%_0%,rgba(255,255,255,0.08),transparent_28%)]" />
              <div className="relative flex flex-wrap items-center gap-3 rounded-full bg-white/10 px-4 py-2 text-sm font-medium backdrop-blur">
                <span className="flex h-2 w-2 rounded-full bg-emerald-300" />
                实时上线 • 安全托管
              </div>
              <h1 className="relative mt-6 text-3xl font-semibold leading-tight md:text-4xl">
                Website Analytics 控制台
              </h1>
              <p className="relative mt-4 max-w-2xl text-white/80">
                轻盈的浅蓝色界面，专注数据洞察与团队协作。登录后可管理数据流、自动报告以及智能助手。
              </p>
              <div className="relative mt-8 grid gap-4 sm:grid-cols-2">
                {features.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.title}
                      className="group rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur transition hover:-translate-y-1 hover:border-white/30"
                    >
                      <div className="mb-3 inline-flex items-center justify-center rounded-xl bg-white/15 p-2 text-sky-100 ring-1 ring-inset ring-white/20">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="text-base font-semibold">{item.title}</div>
                      <p className="mt-1 text-sm text-white/75">{item.desc}</p>
                    </div>
                  );
                })}
              </div>
              <div className="relative mt-10 flex flex-wrap items-center gap-3 text-sm text-white/70">
                <span className="rounded-full bg-white/10 px-3 py-1">99.9% SLA</span>
                <span className="rounded-full bg-white/10 px-3 py-1">最短 10 分钟接入</span>
                <span className="rounded-full bg-white/10 px-3 py-1">支持多角色权限</span>
              </div>
            </div>
          </section>

          <section className="flex items-center justify-center">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white/90 shadow-xl backdrop-blur">
              <div className="border-b border-slate-100 px-8 py-6">
                <p className="text-sm font-medium text-slate-500">欢迎回来</p>
                <h2 className="mt-1 text-2xl font-semibold text-slate-900">登录控制台</h2>
                <p className="mt-2 text-sm text-slate-500">
                  使用用户名和密码登录。当前仅支持 admin/admin，后续可对接真实后端。
                </p>
              </div>

              <div className="px-8 py-8">
                <Form {...form}>
                  <form
                    className="space-y-6"
                    onSubmit={form.handleSubmit(handleSubmit)}
                    noValidate
                  >
                    <FormField
                      control={form.control}
                      name="username"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>用户名</FormLabel>
                          <FormControl>
                            <Input
                              placeholder="请输入用户名"
                              autoComplete="username"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>密码</FormLabel>
                          <FormControl>
                            <Input
                              type="password"
                              placeholder="请输入密码"
                              autoComplete="current-password"
                              {...field}
                            />
                          </FormControl>
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
                      disabled={form.formState.isSubmitting}
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
          </section>
        </div>
      </div>
    </main>
  );
}


type DashboardProps = {
  onLogout: () => void;
};

function Dashboard({ onLogout }: DashboardProps) {
  const highlightCards = useMemo(
    () => [
      {
        title: "实时在线",
        value: "1,842",
        change: "+12.4%",
        tone: "from-emerald-500/10 to-emerald-600/10 text-emerald-700 border-emerald-100"
      },
      {
        title: "转化率",
        value: "4.8%",
        change: "+0.6%",
        tone: "from-sky-500/10 to-sky-600/10 text-sky-700 border-sky-100"
      },
      {
        title: "平均会话",
        value: "6m 12s",
        change: "+9.1%",
        tone: "from-violet-500/10 to-indigo-600/10 text-indigo-700 border-indigo-100"
      }
    ],
    []
  );

  return (
    <DashboardShell
      title="概览仪表板"
      description="左侧为常驻导航，右侧展示首页组件。登录后可浏览报表、漏斗、留存、设置等页面。"
      actions={
        <>
          <Button variant="outline" onClick={onLogout}>
            退出登录
          </Button>
          <Button className="bg-gradient-to-r from-sky-600 to-cyan-500 text-white shadow-lg shadow-sky-200 hover:from-sky-700 hover:to-cyan-600">
            导出报告
          </Button>
        </>
      }
    >
      <section className="grid gap-4 md:grid-cols-3">
        {highlightCards.map((card) => (
          <div
            key={card.title}
            className={cn(
              "rounded-2xl border bg-gradient-to-br p-5 shadow-sm backdrop-blur",
              card.tone
            )}
          >
            <p className="text-sm text-slate-600">{card.title}</p>
            <div className="mt-2 text-3xl font-semibold">{card.value}</div>
            <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {card.change} vs 上一周期
            </div>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-500">过去 7 小时</p>
              <h3 className="text-lg font-semibold text-slate-900">访客趋势</h3>
            </div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
              实时刷新中
            </div>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ReLineChart data={visitsTrend}>
                <defs>
                  <linearGradient id="uvGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.65} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="uv"
                  stroke="#0ea5e9"
                  strokeWidth={2.4}
                  dot={{ r: 4, fill: "#0ea5e9" }}
                  activeDot={{ r: 6 }}
                  fill="url(#uvGradient)"
                />
                <Line
                  type="monotone"
                  dataKey="pv"
                  stroke="#6366f1"
                  strokeDasharray="4 3"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#6366f1" }}
                />
              </ReLineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-500">渠道分布</p>
              <h3 className="text-lg font-semibold text-slate-900">来源占比</h3>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              稳定
            </span>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={channelShare}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" unit="%" />
                <Tooltip />
                <Bar dataKey="value" radius={[8, 8, 4, 4]}>
                  {channelShare.map((item) => (
                    <Cell key={item.name} fill={item.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-500">留存曲线</p>
              <h3 className="text-lg font-semibold text-slate-900">30 日留存</h3>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
              SaaS 默认模型
            </span>
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={retentionData}>
                <defs>
                  <linearGradient id="retentionGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.6} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" unit="%" />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="rate"
                  stroke="#16a34a"
                  strokeWidth={2.4}
                  fillOpacity={1}
                  fill="url(#retentionGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800 p-5 text-white shadow-lg">
          <p className="text-sm text-slate-300">快速要点</p>
          <h3 className="mt-2 text-xl font-semibold">实时提示</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-100/90">
            <li>• 自然搜索流量占比下滑 3.1%，建议补充长尾词投放。</li>
            <li>• 社交分享留存明显优于广告，社群裂变可继续加码。</li>
            <li>• 高峰在 14:00-15:00，活动推送可集中在此时间窗。</li>
          </ul>
          <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur">
            <p className="text-xs uppercase tracking-wide text-white/70">下个版本</p>
            <p className="mt-2 text-sm text-white/90">
              你可以将这里替换为「快速入口」或「看板收藏夹」，用于承载真实业务。
            </p>
          </div>
        </div>
      </section>
    </DashboardShell>
  );
}
