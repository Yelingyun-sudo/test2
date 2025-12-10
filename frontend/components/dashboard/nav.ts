import type { ComponentType } from "react";
import {
  CircleOff,
  ClipboardCheck,
  FilePieChart,
  LayoutDashboard,
  ListChecks,
  Settings,
  Sparkles
} from "lucide-react";

export type DashboardNavItem = {
  title: string;
  href: string;
  desc?: string;
  status?: string;
  icon: ComponentType<{ className?: string }>;
};

export const dashboardNavItems: DashboardNavItem[] = [
  {
    title: "概览仪表板",
    href: "/",
    desc: "首页概览，趋势与渠道卡片。",
    status: "可用",
    icon: LayoutDashboard
  },
  {
    title: "未订阅网站",
    href: "/unsubscribed",
    desc: "待订阅列表、可扩展批量操作。",
    status: "规划中",
    icon: CircleOff
  },
  {
    title: "已订阅网站",
    href: "/subscribed",
    desc: "订阅列表，分页检索。",
    status: "可用",
    icon: ListChecks
  },
  {
    title: "任务中心",
    href: "/tasks",
    desc: "任务列表、进度、操作入口。",
    status: "可用",
    icon: ClipboardCheck
  },
  {
    title: "报表中心",
    href: "/reports",
    desc: "周报/月报模版，PDF 导出。",
    status: "可用",
    icon: FilePieChart
  },
  {
    title: "设置与权限",
    href: "/settings",
    desc: "成员、角色、通知策略。",
    status: "规划中",
    icon: Settings
  }
];
