"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { dashboardNavItems } from "./nav";

type DashboardShellProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
};

export function DashboardShell({ title, description, actions, children }: DashboardShellProps) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/");
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    router.replace("/");
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6 lg:px-8">
        <aside className="sticky top-6 hidden h-[calc(100vh-3rem)] w-64 flex-col rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-sm backdrop-blur lg:flex">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-xl px-3 py-2 transition hover:bg-slate-100"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br from-sky-600 to-cyan-500 text-base font-semibold text-white shadow">
              WA
            </div>
            <div>
              <p className="text-base font-semibold text-slate-900 whitespace-nowrap">
                Website Analytics
              </p>
              <p className="text-sm text-slate-500">用户控制台</p>
            </div>
          </Link>

          <nav className="mt-4 flex-1 space-y-1">
            {dashboardNavItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                    active
                      ? "bg-slate-900 text-white shadow"
                      : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="flex-1 truncate">{item.title}</span>
                  {item.status === "可用" && (
                    <span className="rounded-full bg-white/20 px-2 py-0.5 text-[11px] font-semibold text-white group-hover:bg-white/30">
                      Live
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          <div className="px-1">
            <Button variant="outline" className="w-full justify-center" onClick={handleLogout}>
              退出登录
            </Button>
          </div>
        </aside>

        <div className="flex-1">
          <div className="mb-4 flex flex-col gap-3 lg:hidden">
            <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div>
                <p className="text-base font-semibold text-slate-900 whitespace-nowrap">
                  Website Analytics
                </p>
                <p className="text-sm text-slate-500">用户控制台</p>
              </div>
              <Button size="sm" variant="outline" onClick={handleLogout}>
                退出
              </Button>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
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
    </div>
  );
}
