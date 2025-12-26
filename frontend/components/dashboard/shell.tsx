"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ReactNode, useCallback, useEffect, useState } from "react";
import { ChevronDown, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { clearLocalAuth, isJwtExpired, queueAuthExpiredToast } from "@/lib/api";
import { cn } from "@/lib/utils";

import { dashboardNavItems } from "./nav";

// 全局时间范围选项
const timeRangeOptions: Array<{ value: string; label: string }> = [
  { value: "today", label: "今天" },
  { value: "yesterday", label: "昨天" },
  { value: "3d", label: "最近3天" },
  { value: "7d", label: "最近7天" },
  { value: "30d", label: "最近30天" },
  { value: "ALL", label: "全部" }
];

type DashboardShellProps = {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  account?: string;
  onLogout?: () => void;
};

export function DashboardShell({ title, description, actions, children, account, onLogout }: DashboardShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [accountName, setAccountName] = useState<string | null>(account ?? null);

  // 从 URL 读取时间范围，默认为 "today"
  const timeRange = searchParams.get("time_range") || "today";

  // 切换时间范围时更新 URL 参数
  const handleTimeRangeChange = useCallback((value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "today") {
      params.delete("time_range");
    } else {
      params.set("time_range", value);
    }
    const queryString = params.toString();
    router.push(`${pathname}${queryString ? `?${queryString}` : ""}`);
  }, [pathname, router, searchParams]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("access_token");
    const savedAccount = localStorage.getItem("account_name");
    if (!token) {
      router.replace("/");
      return;
    }
    if (isJwtExpired(token)) {
      clearLocalAuth();
      queueAuthExpiredToast();
      window.location.replace("/");
      return;
    }
    if (!accountName && savedAccount) {
      setAccountName(savedAccount);
    }
  }, [router, accountName]);

  const handleLogout = () => {
    if (onLogout) {
      onLogout();
    } else {
      clearLocalAuth();
    }
    router.replace("/");
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 lg:px-8">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-xl px-2 py-1 transition hover:bg-slate-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-sky-600 to-cyan-500 text-sm font-semibold text-white shadow">
              WA
            </div>
            <div className="hidden sm:block">
              <p className="text-base font-semibold text-slate-900 whitespace-nowrap">
                Website Analytics
              </p>
              <p className="text-sm text-slate-500">控制台</p>
            </div>
          </Link>

          <nav className="hidden flex-1 items-center gap-2 md:flex">
            {dashboardNavItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium transition",
                    active
                      ? "bg-slate-900 text-white shadow-sm"
                      : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.title}</span>
                </Link>
              );
            })}
          </nav>

          {/* 全局时间范围选择器 */}
          <div className="hidden md:block">
            <Select value={timeRange} onValueChange={handleTimeRangeChange}>
              <SelectTrigger className="w-[120px] h-9 border-slate-200 bg-white/80 text-sm font-medium shadow-sm hover:bg-white">
                <SelectValue placeholder="今天" />
              </SelectTrigger>
              <SelectContent>
                {timeRangeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="ml-auto md:ml-0">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="hidden md:flex items-center gap-2 rounded-lg bg-transparent px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100/50 hover:scale-105 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-offset-1">
                  <span>{accountName || "用户"}</span>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="mx-auto block max-w-7xl px-4 pb-3 md:hidden lg:px-8">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <div>
              <p className="text-base font-semibold text-slate-900 whitespace-nowrap">
                Website Analytics
              </p>
              <p className="text-sm text-slate-500">控制台</p>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 rounded-lg bg-transparent px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100/50 hover:scale-105 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-offset-1">
                  <span>{accountName || "用户"}</span>
                  <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {dashboardNavItems.map((item) => {
              const active = pathname === item.href;
              return (
                <Link key={item.href} href={item.href}>
                  <Button
                    size="sm"
                    variant={active ? "default" : "outline"}
                    className={cn(
                      "whitespace-nowrap",
                      active
                        ? "bg-slate-900 text-white"
                        : "border-slate-200 bg-white text-slate-700"
                    )}
                  >
                    {item.title}
                  </Button>
                </Link>
              );
            })}
          </div>
          {/* 移动端时间范围选择器 */}
          <div className="mt-2">
            <Select value={timeRange} onValueChange={handleTimeRangeChange}>
              <SelectTrigger className="w-full h-9 border-slate-200 bg-white text-sm font-medium shadow-sm">
                <SelectValue placeholder="今天" />
              </SelectTrigger>
              <SelectContent>
                {timeRangeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <div className="space-y-6">
          {(title || description) && (
            <div className="rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  {title && (
                    <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
                  )}
                  {description ? (
                    <p className="mt-1 text-sm text-slate-500">{description}</p>
                  ) : null}
                </div>
                {actions ? (
                  <div className="flex flex-wrap items-center gap-3">{actions}</div>
                ) : null}
              </div>
            </div>
          )}

          <div className="space-y-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
