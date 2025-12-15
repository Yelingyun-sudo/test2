"use client";

import { ThemeProvider } from "next-themes";
import { Toaster, toast } from "sonner";
import { useEffect } from "react";

import { popAuthExpiredToast } from "@/lib/api";

type ProvidersProps = {
  children: React.ReactNode;
};

export function Providers({ children }: ProvidersProps) {
  useEffect(() => {
    const message = popAuthExpiredToast();
    if (message) toast.error(message);
  }, []);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
      <Toaster richColors position="top-center" />
    </ThemeProvider>
  );
}
