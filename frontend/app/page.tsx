"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { DashboardShell } from "@/components/dashboard/shell";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { clearLocalAuth, isJwtExpired } from "@/lib/api";

const schema = z.object({
  username: z.string().min(1, "请输入用户名"),
  password: z.string().min(1, "请输入密码")
});

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

type FormValues = z.infer<typeof schema>;

export default function Page() {
  const router = useRouter();
  const [isAuthed, setIsAuthed] = useState(false);
  const [account, setAccount] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: ""
    }
  });

  useEffect(() => {
    setHydrated(true);
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("access_token");
    const savedAccount = localStorage.getItem("account_name");
    if (token && isJwtExpired(token)) {
      clearLocalAuth();
      toast.error("登录已过期，请重新登录");
      setIsAuthed(false);
      setAccount(null);
      return;
    }
    if (token) setIsAuthed(true);
    if (savedAccount) setAccount(savedAccount);
  }, []);

  const handleSubmit = async (values: FormValues) => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(values)
      });

      const data = (await res.json().catch(() => null)) as
        | { access_token?: string; detail?: string }
        | null;

      if (!res.ok) {
        const errorMessage = data?.detail ?? "登录失败，请检查账号密码。";
        throw new Error(errorMessage);
      }

      if (data?.access_token) {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("account_name", values.username);
        setAccount(values.username);
        setIsAuthed(true);
        toast.success("登录成功", { duration: 1000 });
        // 登录成功后跳转到订阅链接任务 Dashboard
        router.push("/subscription");
        return;
      }

      toast.success("登录成功", { duration: 1000 });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "登录失败，请稍后重试或联系管理员。";
      toast.error(message, { duration: 2000 });
    }
  };

  const handleLogout = () => {
    clearLocalAuth();
    setIsAuthed(false);
    setAccount(null);
    toast.success("已退出登录", { duration: 2000 });
  };

  // 水合完成前显示加载状态，避免登录框闪烁
  if (!hydrated) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
        </div>
      </main>
    );
  }

  if (isAuthed) {
    return (
      <DashboardShell
        title="系统概览"
        description="系统概览与数据汇总（建设中）"
        account={account ?? undefined}
        onLogout={handleLogout}
      >
        <div className="flex min-h-[400px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
          <div className="text-center">
            <div className="mb-2 text-4xl">🏗️</div>
            <div className="text-lg font-medium text-slate-700">
              页面建设中
            </div>
            <div className="mt-1 text-sm text-slate-500">
              系统概览功能即将上线
            </div>
          </div>
        </div>
      </DashboardShell>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
      <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-6 py-12 -mt-10">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white/90 shadow-xl backdrop-blur">
          <div className="border-b border-slate-100 px-8 py-6 text-center">
            <h2 className="mt-1 text-2xl font-semibold text-slate-900">Website Analytics 控制台</h2>
          </div>

          <div className="px-8 py-8">
            <Form {...form}>
              <form
                className="space-y-6"
                onSubmit={form.handleSubmit(handleSubmit)}
                method="post"
                noValidate
              >
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem className="space-y-2">
                      <div className="flex items-center gap-3">
                        <FormLabel className="w-14 shrink-0 text-left">账号</FormLabel>
                        <FormControl className="flex-1">
                          <Input
                            placeholder="请输入账号"
                            autoComplete="username"
                            {...field}
                          />
                        </FormControl>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem className="space-y-2">
                      <div className="flex items-center gap-3">
                        <FormLabel className="w-14 shrink-0 text-left">密码</FormLabel>
                        <FormControl className="flex-1">
                          <Input
                            type="password"
                            placeholder="请输入密码"
                            autoComplete="current-password"
                            {...field}
                          />
                        </FormControl>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  className={cn(
                    "inline-flex w-full items-center justify-center gap-2",
                    "bg-gradient-to-r from-sky-600 to-cyan-500 text-white shadow-lg shadow-sky-200",
                    "hover:from-sky-700 hover:to-cyan-600"
                  )}
                  disabled={!hydrated || form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting ? (
                    <span className="flex items-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                      登录中...
                    </span>
                  ) : (
                    <>
                      登录
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>
            </Form>
          </div>
        </div>
      </div>
    </main>
  );
}
