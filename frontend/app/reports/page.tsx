"use client";

import { Download, FilePieChart, Sparkles } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";

const reportTrend = [
  { name: "Mon", downloads: 120 },
  { name: "Tue", downloads: 168 },
  { name: "Wed", downloads: 210 },
  { name: "Thu", downloads: 185 },
  { name: "Fri", downloads: 236 },
  { name: "Sat", downloads: 198 },
  { name: "Sun", downloads: 254 }
];

export default function ReportsPage() {
  return (
    <DashboardShell
      title="运营/增长周报"
      description="模版化输出 PDF/PNG，包含核心 KPI、趋势与亮点，支持一键分享。"
      actions={
        <>
          <Button variant="outline">导出为 PDF</Button>
          <Button className="bg-gradient-to-r from-sky-600 to-cyan-500 text-white shadow-lg shadow-sky-200 hover:from-sky-700 hover:to-cyan-600">
            <Download className="mr-2 h-4 w-4" />
            生成本周报告
          </Button>
        </>
      }
    >
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { title: "访客总量", value: "128,930", change: "+5.2%" },
          { title: "转化次数", value: "3,248", change: "+2.1%" },
          { title: "跳出率", value: "38.4%", change: "-1.3%" }
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm"
          >
            <p className="text-sm text-slate-500">{item.title}</p>
            <div className="mt-2 text-2xl font-semibold text-slate-900">{item.value}</div>
            <p className="mt-1 text-xs text-emerald-600">{item.change} vs 上周</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-500">周内下载</p>
              <h3 className="text-lg font-semibold text-slate-900">报告导出趋势</h3>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
              每日 18:00 更新
            </span>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={reportTrend}>
                <defs>
                  <linearGradient id="downloadGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.6} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="downloads"
                  stroke="#0ea5e9"
                  strokeWidth={2.4}
                  fillOpacity={1}
                  fill="url(#downloadGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-100 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 p-5 text-white shadow-lg">
          <div className="flex items-center gap-2">
            <FilePieChart className="h-5 w-5 text-sky-300" />
            <p className="text-sm text-slate-200">推荐结构</p>
          </div>
          <h3 className="mt-2 text-xl font-semibold">报告模版建议</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-100/90">
            <li>• 首页：关键 KPI 与摘要（同比/环比）。</li>
            <li>• 章节：流量、转化、留存、渠道 ROI，配 2-3 张核心图表。</li>
            <li>• 附录：本周亮点/异常、行动项、负责人。</li>
          </ul>
          <div className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-2 text-xs text-slate-100">
            <Sparkles className="h-4 w-4 text-amber-300" />
            左侧菜单常驻，任意页可一键回到仪表板。
          </div>
        </div>
      </section>
    </DashboardShell>
  );
}
