"use client";

import { Clock, Sparkles } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";

export default function CohortsPage() {
  return (
    <DashboardShell
      title="Cohort 留存"
      description="按注册周/渠道的留存矩阵、回访率，以及分层留存曲线。"
      actions={
        <Button variant="outline">
          <Clock className="mr-2 h-4 w-4" />
          即将上线
        </Button>
      }
    >
      <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-6 text-slate-700 shadow-sm">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-1 h-5 w-5 text-emerald-500" />
          <div>
            <p className="text-sm font-semibold text-slate-900">页面布局建议</p>
            <ul className="mt-2 space-y-2 text-sm text-slate-600">
              <li>• 顶部：日期与渠道筛选、导出按钮。</li>
              <li>• 左：留存矩阵（按 cohort 列、按日/周行）。</li>
              <li>• 右：分 cohort 曲线 + 快速洞察卡片。</li>
            </ul>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
