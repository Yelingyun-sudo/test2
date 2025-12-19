"use client";

import { useMemo } from "react";
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

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { DashboardShell } from "./shell";

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

type DashboardProps = {
  onLogout: () => void;
  account?: string;
};

export function Dashboard({ onLogout, account }: DashboardProps) {
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
      account={account}
      title="概览仪表板"
      description="左侧为常驻导航，右侧展示首页组件。登录后可浏览报表、漏斗、留存、设置等页面。"
      onLogout={onLogout}
      actions={
        <Button className="bg-gradient-to-r from-sky-600 to-cyan-500 text-white shadow-lg shadow-sky-200 hover:from-sky-700 hover:to-cyan-600">
          导出报告
        </Button>
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

