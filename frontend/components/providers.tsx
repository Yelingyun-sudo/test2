"use client";

import { ThemeProvider } from "next-themes";
import { Toaster, toast } from "sonner";
import { useEffect } from "react";

import { popAuthExpiredToast } from "@/lib/api";
import { DateRangeProvider } from "@/lib/date-range-context";

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
      <DateRangeProvider>
        {children}
        <Toaster richColors position="top-center" />
      </DateRangeProvider>
    </ThemeProvider>
  );
}
