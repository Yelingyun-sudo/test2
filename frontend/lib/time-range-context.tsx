"use client";

import { createContext, useContext, useState, ReactNode } from "react";
import { startOfToday } from "date-fns";
import type { DateRange } from "@/components/subscription/time-range-selector";

type TimeRangeContextType = {
  dateRange: DateRange;
  setDateRange: (range: DateRange) => void;
};

const TimeRangeContext = createContext<TimeRangeContextType | undefined>(undefined);

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [dateRange, setDateRange] = useState<DateRange>(() => {
    const today = startOfToday();
    return { from: today, to: today };
  });

  return (
    <TimeRangeContext.Provider value={{ dateRange, setDateRange }}>
      {children}
    </TimeRangeContext.Provider>
  );
}

export function useTimeRange() {
  const context = useContext(TimeRangeContext);
  if (!context) {
    throw new Error("useTimeRange must be used within TimeRangeProvider");
  }
  return context;
}

