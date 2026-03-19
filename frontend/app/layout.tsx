import type { Metadata } from "next";
import { Sora } from "next/font/google";


// 这个 layout.tsx 文件是 Next.js 框架应用中的根布局文件。在 Next.js 的 App Router 架构下，它是整个应用的“外壳”，
// 所有页面（如首页、登录页、控制台页）都会被包裹在这个布局结构内部渲染。
// 简单来说，它负责定义整个网页通用的字体、语言、元数据（SEO）以及全局上下文环境。

import { Providers } from "@/components/providers";
import { cn } from "@/lib/utils";
import "./globals.css";

// 引入并配置 Google 字体 Sora。
const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  weight: ["400", "500", "600", "700"]
});

// 2. 元数据定义
export const metadata: Metadata = {
  title: "Website Analytics | 登录",
  description: "登录 Website Analytics 控制台"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={cn("min-h-screen bg-background font-sans", sora.variable)}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
