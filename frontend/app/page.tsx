"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowRight,
  LineChart,
  ShieldCheck,
  Sparkles,
  UserRound
} from "lucide-react";
import { useForm } from "react-hook-form";
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
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const schema = z.object({
  username: z.string().min(1, "请输入用户名"),
  password: z.string().min(1, "请输入密码")
});

const features = [
  {
    title: "安全合规",
    desc: "数据按角色隔离，支持精细化审计。",
    icon: ShieldCheck
  },
  {
    title: "实时洞察",
    desc: "秒级看板刷新，异常自动提醒。",
    icon: LineChart
  },
  {
    title: "智能助理",
    desc: "用自然语言提问，快速生成报告。",
    icon: Sparkles
  },
  {
    title: "团队协作",
    desc: "多成员并行操作，记录可追溯。",
    icon: UserRound
  }
];

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

type FormValues = z.infer<typeof schema>;

export default function Page() {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: ""
    }
  });

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
      }

      toast.success("登录成功", {
        description: "已通过 admin/admin 静态校验，后续可接入真实鉴权。"
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "登录失败，请稍后重试或联系管理员。";
      toast.error(message);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
      <div className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-12">
        <div className="grid w-full gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-800 via-sky-600 to-cyan-500 p-[1px] shadow-2xl">
            <div className="grainy relative h-full w-full rounded-[calc(1.5rem-1px)] bg-gradient-to-br from-sky-950/50 via-sky-900/40 to-sky-800/50 px-8 py-10 text-white">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.12),transparent_32%),radial-gradient(circle_at_80%_0%,rgba(255,255,255,0.08),transparent_28%)]" />
              <div className="relative flex flex-wrap items-center gap-3 rounded-full bg-white/10 px-4 py-2 text-sm font-medium backdrop-blur">
                <span className="flex h-2 w-2 rounded-full bg-emerald-300" />
                实时上线 • 安全托管
              </div>
              <h1 className="relative mt-6 text-3xl font-semibold leading-tight md:text-4xl">
                Website Analytics 控制台
              </h1>
              <p className="relative mt-4 max-w-2xl text-white/80">
                轻盈的浅蓝色界面，专注数据洞察与团队协作。登录后可管理数据流、自动报告以及智能助手。
              </p>
              <div className="relative mt-8 grid gap-4 sm:grid-cols-2">
                {features.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.title}
                      className="group rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur transition hover:-translate-y-1 hover:border-white/30"
                    >
                      <div className="mb-3 inline-flex items-center justify-center rounded-xl bg-white/15 p-2 text-sky-100 ring-1 ring-inset ring-white/20">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="text-base font-semibold">{item.title}</div>
                      <p className="mt-1 text-sm text-white/75">{item.desc}</p>
                    </div>
                  );
                })}
              </div>
              <div className="relative mt-10 flex flex-wrap items-center gap-3 text-sm text-white/70">
                <span className="rounded-full bg-white/10 px-3 py-1">99.9% SLA</span>
                <span className="rounded-full bg-white/10 px-3 py-1">最短 10 分钟接入</span>
                <span className="rounded-full bg-white/10 px-3 py-1">支持多角色权限</span>
              </div>
            </div>
          </section>

          <section className="flex items-center justify-center">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white/90 shadow-xl backdrop-blur">
              <div className="border-b border-slate-100 px-8 py-6">
                <p className="text-sm font-medium text-slate-500">欢迎回来</p>
                <h2 className="mt-1 text-2xl font-semibold text-slate-900">登录控制台</h2>
                <p className="mt-2 text-sm text-slate-500">
                  使用用户名和密码登录。当前仅支持 admin/admin，后续可对接真实后端。
                </p>
              </div>

              <div className="px-8 py-8">
                <Form {...form}>
                  <form
                    className="space-y-6"
                    onSubmit={form.handleSubmit(handleSubmit)}
                    noValidate
                  >
                    <FormField
                      control={form.control}
                      name="username"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>用户名</FormLabel>
                          <FormControl>
                            <Input
                              placeholder="请输入用户名"
                              autoComplete="username"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>密码</FormLabel>
                          <FormControl>
                            <Input
                              type="password"
                              placeholder="请输入密码"
                              autoComplete="current-password"
                              {...field}
                            />
                          </FormControl>
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
                      disabled={form.formState.isSubmitting}
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
          </section>
        </div>
      </div>
    </main>
  );
}
