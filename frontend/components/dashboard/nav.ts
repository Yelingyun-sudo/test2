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
    desc: "首页概览（建设中）",
    status: "规划中",
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
    desc: "订阅链接任务统计与汇总。",
    status: "可用",
    icon: ListChecks
  },
  {
    title: "支付链接任务",
    href: "/payment",
    desc: "支付二维码提取任务统计与汇总。",
    status: "可用",
    icon: CreditCard
  }
];
