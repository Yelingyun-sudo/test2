"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const TIME_RANGE_OPTIONS = [
  { label: "今天", value: "today" },
  { label: "昨天", value: "yesterday" },
  { label: "最近3天", value: "3d" },
  { label: "最近7天", value: "7d" },
  { label: "最近30天", value: "30d" },
  { label: "全部", value: "ALL" }
];

type TimeRangeSelectorProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
};

export function TimeRangeSelector({ value, onChange, className }: TimeRangeSelectorProps) {
  return (
    <Tabs
      value={value}
      onValueChange={onChange}
      className={cn("w-full", className)}
    >
      <TabsList className="inline-flex h-10 w-full items-center justify-start rounded-lg bg-slate-100 p-1 text-slate-600">
        {TIME_RANGE_OPTIONS.map((option) => (
          <TabsTrigger
            key={option.value}
            value={option.value}
            className="data-[state=active]:bg-white data-[state=active]:text-sky-600 data-[state=active]:shadow-sm data-[state=active]:font-semibold"
          >
            {option.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

