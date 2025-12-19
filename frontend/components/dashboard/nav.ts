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
  }
];
