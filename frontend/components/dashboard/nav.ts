import type { ComponentType } from "react";
import {
  CheckSquare,
  CreditCard,
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
    title: "系统概览",
    href: "/",
    desc: "真实数据概览，统计与趋势。",
    status: "可用",
    icon: LayoutDashboard
  },
  {
    title: "注册取证任务",
    href: "/evidence",
    desc: "注册取证任务列表，支持分页检索。",
    status: "规划中",
    icon: CheckSquare
  },
  {
    title: "订阅链接任务",
    href: "/subscription",
    desc: "订阅链接提取任务，支持筛选与检索。",
    status: "可用",
    icon: ListChecks
  },
  {
    title: "支付链接任务",
    href: "/payment",
    desc: "支付链接任务列表（开发中）",
    status: "规划中",
    icon: CreditCard
  }
];
