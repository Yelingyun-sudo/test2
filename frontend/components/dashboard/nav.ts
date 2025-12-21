import type { ComponentType } from "react";
import {
  CircleOff,
  LayoutDashboard,
  ListChecks
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
    desc: "真实数据概览，统计与趋势。",
    status: "可用",
    icon: LayoutDashboard
  },
  {
    title: "注册取证任务",
    href: "/unsubscribed",
    desc: "注册取证任务列表，支持分页检索。",
    status: "规划中",
    icon: CircleOff
  },
  {
    title: "订阅链接任务",
    href: "/subscribed",
    desc: "订阅链接提取任务，支持筛选与检索。",
    status: "可用",
    icon: ListChecks
  }
];
