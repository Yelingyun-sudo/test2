"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { clearLocalAuth, isJwtExpired } from "@/lib/api";

const RealDashboard = dynamic(
  () =>
    import("@/components/dashboard/real-dashboard").then((mod) => mod.RealDashboard),
  { ssr: false }
);

export default function SubscriptionPage() {
  const router = useRouter();
  const [isAuthed, setIsAuthed] = useState(false);
  const [account, setAccount] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
    if (typeof window === "undefined") return;
    
    const token = localStorage.getItem("access_token");
    const savedAccount = localStorage.getItem("account_name");
    
    if (!token) {
      toast.error("请先登录");
      router.push("/");
      return;
    }
    
    if (isJwtExpired(token)) {
      clearLocalAuth();
      toast.error("登录已过期，请重新登录");
      router.push("/");
      return;
    }
    
    setIsAuthed(true);
    if (savedAccount) setAccount(savedAccount);
  }, [router]);

  const handleLogout = () => {
    clearLocalAuth();
    setIsAuthed(false);
    setAccount(null);
    toast.success("已退出登录", { duration: 2000 });
    router.push("/");
  };

  // 水合完成前或未认证时显示加载状态
  if (!hydrated || !isAuthed) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-slate-50">
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-600" />
        </div>
      </main>
    );
  }

  return (
    <RealDashboard onLogout={handleLogout} account={account ?? undefined} />
  );
}

