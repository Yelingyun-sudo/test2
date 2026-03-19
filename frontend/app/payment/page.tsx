"use client";

import { DashboardShell } from "@/components/dashboard/shell";

export default function PaymentPage() {
  return (
    <DashboardShell>
      <div className="flex min-h-[400px] items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50">
        <div className="text-center p-8">
          <div className="text-6xl mb-4">🚧</div>
          <h2 className="text-2xl font-semibold text-slate-900 mb-2">
            功能开发中
          </h2>
          <p className="text-slate-600">
            支付链接任务功能正在开发中，预计上线时间：2026年 Q1
          </p>
        </div>
      </div>
    </DashboardShell>
  );
}
