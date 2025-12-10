"use client";

import { CheckCircle, Clock3, Play, ShieldCheck } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const tasks = [
  { title: "数据同步", status: "进行中", owner: "数据团队", eta: "12:00", progress: 68 },
  { title: "周报生成", status: "待处理", owner: "运营", eta: "14:00", progress: 0 },
  { title: "巡检告警", status: "已完成", owner: "平台", eta: "10:20", progress: 100 }
];

export default function TasksPage() {
  return (
    <DashboardShell
      title="任务中心"
      description="集中查看任务列表、进度与操作入口，可后续接入真实任务数据。"
      actions={
        <>
          <Button variant="outline">
            <ShieldCheck className="mr-2 h-4 w-4" />
            创建任务
          </Button>
          <Button className="bg-gradient-to-r from-sky-600 to-cyan-500 text-white shadow-lg shadow-sky-200 hover:from-sky-700 hover:to-cyan-600">
            <Play className="mr-2 h-4 w-4" />
            一键执行
          </Button>
        </>
      }
    >
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { title: "进行中", value: "6", tone: "from-sky-500/10 to-sky-600/10 text-sky-700" },
          { title: "待处理", value: "12", tone: "from-amber-500/10 to-amber-600/10 text-amber-700" },
          { title: "已完成", value: "42", tone: "from-emerald-500/10 to-emerald-600/10 text-emerald-700" }
        ].map((item) => (
          <div
            key={item.title}
            className={cn(
              "rounded-2xl border border-slate-100 bg-gradient-to-br p-5 shadow-sm",
              item.tone
            )}
          >
            <p className="text-sm text-slate-700">{item.title}</p>
            <div className="mt-2 text-3xl font-semibold">{item.value}</div>
          </div>
        ))}
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="grid grid-cols-[1.4fr_0.9fr_0.7fr_0.8fr_0.7fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>任务名称</div>
          <div>状态</div>
          <div>负责人</div>
          <div>预计完成</div>
          <div>进度</div>
        </div>
        <div className="divide-y divide-slate-100">
          {tasks.map((task, idx) => (
            <div
              key={task.title}
              className={cn(
                "grid grid-cols-[1.4fr_0.9fr_0.7fr_0.8fr_0.7fr] items-center px-4 py-3 text-sm text-slate-700",
                idx % 2 === 0 ? "bg-white" : "bg-slate-50/70"
              )}
            >
              <div className="flex items-center gap-2">
                <Clock3 className="h-4 w-4 text-slate-400" />
                <span className="truncate">{task.title}</span>
              </div>
              <span
                className={cn(
                  "inline-flex w-fit items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold",
                  task.status === "已完成"
                    ? "bg-emerald-50 text-emerald-700"
                    : task.status === "进行中"
                      ? "bg-sky-50 text-sky-700"
                      : "bg-amber-50 text-amber-700"
                )}
              >
                {task.status === "已完成" && <CheckCircle className="h-3.5 w-3.5" />}
                {task.status}
              </span>
              <span>{task.owner}</span>
              <span>{task.eta}</span>
              <div className="flex items-center gap-2">
                <div className="h-2 w-full rounded-full bg-slate-100">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-sky-500 to-cyan-500"
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs text-slate-500">{task.progress}%</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </DashboardShell>
  );
}
