"use client";

import { useState, useEffect } from "react";
import { format, subDays, startOfToday, startOfYesterday, isSameDay } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { CalendarIcon, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DateRange as ReactDayPickerRange } from "react-day-picker";

export type DateRange = {
  from: Date | undefined;
  to: Date | undefined;
};

type TimeRangeSelectorProps = {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
  variant?: "tabs" | "select";
};

// 格式化日期显示标签
function formatDateLabel(date: Date): string {
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

// 格式化日期范围显示文本
function formatDateRange(range: DateRange): string {
  if (!range.from && !range.to) {
    return "全部时间";
  }
  if (range.from && range.to) {
    if (isSameDay(range.from, range.to)) {
      return formatDateLabel(range.from);
    }
    return `${formatDateLabel(range.from)} ~ ${formatDateLabel(range.to)}`;
  }
  if (range.from) {
    return `${formatDateLabel(range.from)} ~`;
  }
  if (range.to) {
    return `~ ${formatDateLabel(range.to)}`;
  }
  return "选择日期";
}

// 获取预设日期范围
function getPresetRange(preset: string): DateRange {
  const today = startOfToday();
  const yesterday = startOfYesterday();

  switch (preset) {
    case "today":
      return { from: today, to: today };
    case "yesterday":
      return { from: yesterday, to: yesterday };
    case "3d":
      return { from: subDays(today, 2), to: today };
    case "7d":
      return { from: subDays(today, 6), to: today };
    case "30d":
      return { from: subDays(today, 29), to: today };
    case "ALL":
      return { from: undefined, to: undefined };
    default:
      return { from: today, to: today };
  }
}

// 比较两个日期是否在同一天（只比较日期部分，忽略时间）
function isSameDate(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}

// 将 DateRange 转换为后端 time_range 参数（向后兼容）
function dateRangeToTimeRange(range: DateRange): string {
  if (!range.from && !range.to) {
    return "ALL";
  }
  
  if (!range.from || !range.to) {
    // 如果只有开始或结束日期，返回 today
    return "today";
  }
  
  // 检查是否为单日
  if (isSameDate(range.from, range.to)) {
    // 检查是否为预设的单日（今天或昨天）
    const today = startOfToday();
    const yesterday = startOfYesterday();
    
    if (isSameDate(range.from, today)) {
      return "today";
    }
    if (isSameDate(range.from, yesterday)) {
      return "yesterday";
    }
    // 其他单日，返回日期格式
    return format(range.from, "yyyy-MM-dd");
  }
  
  // 检查是否为预设的日期范围
  const today = startOfToday();
  const presetRanges = [
    { preset: "3d", from: subDays(today, 2), to: today },
    { preset: "7d", from: subDays(today, 6), to: today },
    { preset: "30d", from: subDays(today, 29), to: today },
  ];
  
  for (const preset of presetRanges) {
    if (isSameDate(range.from, preset.from) && isSameDate(range.to, preset.to)) {
      return preset.preset;
    }
  }
  
  // 如果是自定义日期范围，暂时返回 today（后续需要后端支持 start_date/end_date）
  return "today";
}

// 将后端 time_range 参数转换为 DateRange（向后兼容）
function timeRangeToDateRange(timeRange: string): DateRange {
  if (!timeRange || timeRange === "ALL") {
    return { from: undefined, to: undefined };
  }
  // 检测是否为日期格式 YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(timeRange)) {
    const date = new Date(timeRange);
    return { from: date, to: date };
  }
  // 预设值
  return getPresetRange(timeRange);
}

export function TimeRangeSelector({ 
  value, 
  onChange, 
  className,
  variant = "select"
}: TimeRangeSelectorProps) {
  const [open, setOpen] = useState(false);
  const [selectedRange, setSelectedRange] = useState<ReactDayPickerRange | undefined>(
    value.from || value.to ? { from: value.from, to: value.to } : undefined
  );

  // 同步 selectedRange 与 value
  useEffect(() => {
    if (value.from || value.to) {
      setSelectedRange({ from: value.from, to: value.to });
    } else {
      setSelectedRange(undefined);
    }
  }, [value]);

  // 快捷选择预设
  const presets = [
    { label: "今天", preset: "today" },
    { label: "昨天", preset: "yesterday" },
    { label: "最近3天", preset: "3d" },
    { label: "最近7天", preset: "7d" },
    { label: "最近30天", preset: "30d" },
    { label: "全部", preset: "ALL" },
  ];

  const handlePresetClick = (preset: string) => {
    const range = getPresetRange(preset);
    onChange(range);
    setOpen(false);
  };

  const handleDateRangeSelect = (range: ReactDayPickerRange | undefined) => {
    setSelectedRange(range);
    if (range?.from && range?.to) {
      // 只有选择了完整范围才更新
      onChange({ from: range.from, to: range.to });
      setOpen(false);
    } else if (range?.from) {
      // 只选择了开始日期，先更新开始日期
      onChange({ from: range.from, to: undefined });
    }
  };

  const displayText = formatDateRange(value);

  if (variant === "tabs") {
    // Tabs 模式：只显示日期范围选择器
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className={cn(
              "h-10 min-w-[200px] justify-start text-left font-normal",
              !value.from && !value.to && "text-slate-500",
              className
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4 flex-shrink-0" />
            <span className="truncate">{displayText}</span>
            <ChevronDown className="ml-auto h-4 w-4 opacity-50 flex-shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="end">
          <div className="p-3 border-b">
            <div className="flex flex-wrap gap-2">
              {presets.map((preset) => (
                <Button
                  key={preset.preset}
                  variant="ghost"
                  size="sm"
                  className="h-8 px-3 text-sm"
                  onClick={() => handlePresetClick(preset.preset)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>
          <Calendar
            mode="range"
            selected={selectedRange}
            onSelect={handleDateRangeSelect}
            numberOfMonths={2}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    );
  }

  // Select 模式（默认）：日期范围输入框样式
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "h-10 min-w-[200px] justify-start text-left font-normal",
            !value.from && !value.to && "text-slate-500",
            className
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4 flex-shrink-0" />
          <span className="truncate">{displayText}</span>
          <ChevronDown className="ml-auto h-4 w-4 opacity-50 flex-shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="p-3 border-b">
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <Button
                key={preset.preset}
                variant="ghost"
                size="sm"
                className="h-8 px-3 text-sm"
                onClick={() => handlePresetClick(preset.preset)}
              >
                {preset.label}
              </Button>
            ))}
          </div>
        </div>
        <Calendar
          mode="range"
          selected={selectedRange}
          onSelect={handleDateRangeSelect}
          numberOfMonths={2}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}

// 导出辅助函数供外部使用
export { dateRangeToTimeRange, timeRangeToDateRange, getPresetRange };
