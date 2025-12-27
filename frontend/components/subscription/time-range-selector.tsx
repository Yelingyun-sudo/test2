"use client";

import { useState, useEffect } from "react";
import { format } from "date-fns";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const TIME_RANGE_OPTIONS = [
  { label: "今天", value: "today" },
  { label: "昨天", value: "yesterday" },
  { label: "最近3天", value: "3d" },
  { label: "最近7天", value: "7d" },
  { label: "最近30天", value: "30d" },
  { label: "全部", value: "ALL" },
  { label: "自定义日期", value: "custom" },
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
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(
    isDateFormat(value) ? new Date(value) : undefined
  );
  const [selectDisplayValue, setSelectDisplayValue] = useState<string>(value);

  // 同步 selectedDate 与 value
  useEffect(() => {
    if (isDateFormat(value)) {
      setSelectedDate(new Date(value));
      setSelectDisplayValue(value);
    } else if (value !== "custom") {
      setSelectDisplayValue(value);
    }
  }, [value]);

  // Tabs 模式下，如果值是日期格式，回退到 "ALL"
  const tabsValue = variant === "tabs" && isDateFormat(value) ? "ALL" : value;

  // Select 模式下的显示文本
  const displayLabel = isDateFormat(value)
    ? `📅 ${formatDateLabel(value)}`
    : TIME_RANGE_OPTIONS.find((o) => o.value === value)?.label || "选择时间";

  // 处理 Select 值变化
  const handleValueChange = (val: string) => {
    if (val === "custom") {
      // 选择自定义日期时，打开日历弹窗，但不改变 value
      setCalendarOpen(true);
      // 保持当前的显示值不变
    } else {
      onChange(val);
      setSelectDisplayValue(val);
    }
  };

  // 处理日期选择
  const handleDateSelect = (date: Date | undefined) => {
    setSelectedDate(date);
    if (date) {
      onChange(format(date, "yyyy-MM-dd"));
      setCalendarOpen(false);
    }
  };

  if (variant === "tabs") {
    return (
      <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
        <div className={cn("flex items-center gap-2", className)}>
          <Tabs
            value={tabsValue}
            onValueChange={onChange}
            className="flex-1"
          >
            <TabsList className="inline-flex h-10 w-full items-center justify-start rounded-lg bg-slate-100 p-1 text-slate-600">
              {TIME_RANGE_OPTIONS.filter((option) => option.value !== "custom").map((option) => (
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
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className={cn(
                "h-10 w-10 rounded-lg border-slate-200 bg-white shadow-sm",
                isDateFormat(value) && "bg-sky-50 border-sky-200 text-sky-600"
              )}
            >
              <CalendarIcon className="h-4 w-4" />
            <span className="sr-only">选择自定义日期</span>
            </Button>
          </PopoverTrigger>
        </div>
        <PopoverContent className="w-auto p-0" align="end">
          <Calendar
            mode="single"
            selected={selectedDate}
            onSelect={handleDateSelect}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    );
  }

  // Select 模式（默认）
  return (
    <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
      <div className="relative">
        <Select value={selectDisplayValue} onValueChange={handleValueChange}>
          <SelectTrigger className={cn("w-full", className)}>
            <SelectValue placeholder={displayLabel} />
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
        {/* 隐藏的 PopoverTrigger 作为日历弹窗的定位锚点 */}
        <PopoverTrigger asChild>
          <span className="absolute inset-0 pointer-events-none" aria-hidden="true" />
        </PopoverTrigger>
      </div>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={handleDateSelect}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
