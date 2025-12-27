"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const TIME_RANGE_OPTIONS = [
  { label: "今天", value: "today" },
  { label: "昨天", value: "yesterday" },
  { label: "最近3天", value: "3d" },
  { label: "最近7天", value: "7d" },
  { label: "最近30天", value: "30d" },
  { label: "全部", value: "ALL" },
];

// 检测是否为日期格式 YYYY-MM-DD
function isDateFormat(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

// 格式化日期显示标签
function formatDateLabel(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

type TimeRangeSelectorProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  variant?: "tabs" | "select";
};

export function TimeRangeSelector({ 
  value, 
  onChange, 
  className,
  variant = "select"
}: TimeRangeSelectorProps) {
  // Tabs 模式下，如果值是日期格式，回退到 "ALL"
  const tabsValue = variant === "tabs" && isDateFormat(value) ? "ALL" : value;

  // Select 模式下的显示文本
  const displayLabel = isDateFormat(value)
    ? `📅 ${formatDateLabel(value)}`
    : TIME_RANGE_OPTIONS.find((o) => o.value === value)?.label || "选择时间";

  if (variant === "tabs") {
    return (
      <Tabs
        value={tabsValue}
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

  // Select 模式（默认）
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={cn("w-full", className)}>
        <SelectValue>{displayLabel}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {TIME_RANGE_OPTIONS.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
        {isDateFormat(value) && (
          <>
            <SelectSeparator />
            <SelectItem value={value}>
              📅 {formatDateLabel(value)}
            </SelectItem>
          </>
        )}
      </SelectContent>
    </Select>
  );
}
