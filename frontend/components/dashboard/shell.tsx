"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearLocalAuth, isJwtExpired, queueAuthExpiredToast } from "@/lib/api";
import { cn } from "@/lib/utils";

import { dashboardNavItems } from "./nav";

type DashboardShellProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  account?: string;
  onLogout?: () => void;
};

export function DashboardShell({ title, description, actions, children, account, onLogout }: DashboardShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [accountName, setAccountName] = useState<string | null>(account ?? null);

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

          <div className="ml-auto flex items-center gap-3">
            {accountName ? (
              <div className="flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm">
                {accountName}
              </div>
            ) : null}
            <Button size="sm" variant="outline" onClick={handleLogout} className="hidden md:inline-flex">
              退出登录
            </Button>
          </div>
        </div>

        <div className="mx-auto block max-w-7xl px-4 pb-3 md:hidden lg:px-8">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <div>
              <p className="text-base font-semibold text-slate-900 whitespace-nowrap">
                Website Analytics
              </p>
              <p className="text-sm text-slate-500">控制台</p>
              {accountName ? <p className="mt-1 text-xs text-slate-600">{accountName}</p> : null}
            </div>
            <Button size="sm" variant="outline" onClick={handleLogout}>
              退出登录
            </Button>
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
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
                {description ? (
                  <p className="mt-1 text-sm text-slate-500">{description}</p>
                ) : null}
              </div>
              {actions ? (
                <div className="flex flex-wrap items-center gap-3">{actions}</div>
              ) : null}
            </div>
          </div>

          <div className="space-y-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
