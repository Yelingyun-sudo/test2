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

type DateRangePickerProps = {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
  variant?: "tabs" | "select";
};

// 预设标签映射（显示标签与按钮标签保持一致，但"全部时间"例外）
const PRESET_LABELS: Record<string, string> = {
  today: "今天",
  yesterday: "昨天",
  "3d": "最近3天",
  "7d": "最近7天",
  "30d": "最近30天",
  ALL: "全部时间",
};

// 判断日期范围是否匹配预设值
function matchPresetRange(range: DateRange): string | null {
  // 检查"全部时间"
  if (!range.from && !range.to) {
    return PRESET_LABELS.ALL;
  }

  // 其他预设都需要完整的日期范围
  if (!range.from || !range.to) {
    return null;
  }

  const today = startOfToday();
  const yesterday = startOfYesterday();

  // 检查"今天"
  if (isSameDay(range.from, today) && isSameDay(range.to, today)) {
    return PRESET_LABELS.today;
  }

  // 检查"昨天"
  if (isSameDay(range.from, yesterday) && isSameDay(range.to, yesterday)) {
    return PRESET_LABELS.yesterday;
  }

  // 检查"最近3天"
  const threeDaysAgo = subDays(today, 2);
  if (isSameDay(range.from, threeDaysAgo) && isSameDay(range.to, today)) {
    return PRESET_LABELS["3d"];
  }

  // 检查"最近7天"
  const sevenDaysAgo = subDays(today, 6);
  if (isSameDay(range.from, sevenDaysAgo) && isSameDay(range.to, today)) {
    return PRESET_LABELS["7d"];
  }

  // 检查"最近30天"
  const thirtyDaysAgo = subDays(today, 29);
  if (isSameDay(range.from, thirtyDaysAgo) && isSameDay(range.to, today)) {
    return PRESET_LABELS["30d"];
  }

  return null;
}

// 格式化日期显示标签
function formatDateLabel(date: Date): string {
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

// 格式化日期范围显示文本
function formatDateRange(range: DateRange): string {
  // 先检查是否匹配预设值
  const presetLabel = matchPresetRange(range);
  if (presetLabel) {
    return presetLabel;
  }

  // 如果不匹配预设，使用原有的日期格式化逻辑
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


export function DateRangePicker({
  value,
  onChange,
  className,
  variant = "select"
}: DateRangePickerProps) {
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
export { getPresetRange };
