"use client";

import { Bell, Shield } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  return (
    <DashboardShell
      title="设置与权限"
      description="配置成员、角色、通知、单点登录接入等，保证导航一致性与安全。"
      actions={
        <Button variant="outline">
          <Shield className="mr-2 h-4 w-4" />
          待接入
        </Button>
      }
    >
      <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-6 text-slate-700 shadow-sm">
        <div className="flex items-start gap-3">
          <Bell className="mt-1 h-5 w-5 text-indigo-500" />
          <div>
            <p className="text-sm font-semibold text-slate-900">布局建议</p>
            <ul className="mt-2 space-y-2 text-sm text-slate-600">
              <li>• 左：成员列表与角色；右：权限详情/编辑抽屉。</li>
              <li>• 顶部：主要操作（新增成员/保存），统一风格。</li>
              <li>• 底部：通知策略、Webhooks、SSO/2FA 配置卡片。</li>
            </ul>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
