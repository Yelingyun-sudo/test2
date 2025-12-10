"use client";

import { Compass, Wrench } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";

export default function FunnelsPage() {
  return (
    <DashboardShell
      title="漏斗 & ROI"
      description="展示投放、自然、社交流量的漏斗表现和 ROI，对比渠道与落地页。"
      actions={
        <Button variant="outline">
          <Wrench className="mr-2 h-4 w-4" />
          建设中
        </Button>
      }
    >
      <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-6 text-slate-700 shadow-sm">
        <div className="flex items-start gap-3">
          <Compass className="mt-1 h-5 w-5 text-sky-500" />
          <div>
            <p className="text-sm font-semibold text-slate-900">规划提示</p>
            <ul className="mt-2 space-y-2 text-sm text-slate-600">
              <li>• 顶部：时间/渠道筛选，右侧放导出或分享。</li>
              <li>• 中部：漏斗图 + 渠道对比条形 + ROI 散点。</li>
              <li>• 底部：按落地页/素材分组的明细表格。</li>
            </ul>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
