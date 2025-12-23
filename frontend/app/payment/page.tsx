"use client";

import { DashboardShell } from "@/components/dashboard/shell";

export default function PaymentPage() {
  return (
    <DashboardShell
      title="支付链接任务"
      description="支付链接任务管理（功能开发中）"
    >
      <div className="flex min-h-[400px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
        <div className="text-center">
          <div className="mb-2 text-4xl">🚧</div>
          <div className="text-lg font-medium text-slate-700">
            功能开发中
          </div>
          <div className="mt-1 text-sm text-slate-500">
            支付链接任务管理功能即将上线
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
