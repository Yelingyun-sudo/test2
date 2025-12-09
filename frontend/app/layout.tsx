import type { Metadata } from "next";
import { Sora } from "next/font/google";

import { Providers } from "@/components/providers";
import { cn } from "@/lib/utils";
import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  weight: ["400", "500", "600", "700"]
});

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
