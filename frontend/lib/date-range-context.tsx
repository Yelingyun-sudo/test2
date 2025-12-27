"use client";

import { createContext, useContext, useState, ReactNode } from "react";
import { startOfToday } from "date-fns";
import type { DateRange } from "@/components/ui/date-range-picker";

type DateRangeContextType = {
  dateRange: DateRange;
  setDateRange: (range: DateRange) => void;
};

const DateRangeContext = createContext<DateRangeContextType | undefined>(undefined);

export function DateRangeProvider({ children }: { children: ReactNode }) {
  const [dateRange, setDateRange] = useState<DateRange>(() => {
    const today = startOfToday();
    return { from: today, to: today };
  });

  return (
    <DateRangeContext.Provider value={{ dateRange, setDateRange }}>
      {children}
    </DateRangeContext.Provider>
  );
}

export function useDateRange() {
  const context = useContext(DateRangeContext);
  if (!context) {
    throw new Error("useDateRange must be used within DateRangeProvider");
  }
  return context;
}

