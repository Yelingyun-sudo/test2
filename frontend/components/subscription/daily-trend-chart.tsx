"use client";

import {
  CartesianGrid,
  ComposedChart,
  Bar,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { DailyTrendItem } from "@/lib/types";

type DailyTrendChartProps = {
  dailyTrend: DailyTrendItem[];
  days?: number; // 显示最近多少天，默认5天
  showViewDetails?: boolean;
  onViewDetails?: () => void;
  onDateClick?: (date: string) => void; // 点击日期回调，传递 YYYY-MM-DD 格式
};

export function DailyTrendChart({
  dailyTrend,
  days = 5,
  showViewDetails = false,
  onViewDetails,
  onDateClick
}: DailyTrendChartProps) {
  // 处理图表数据（只显示最近N天），保留原始日期用于点击事件
  const trendData = dailyTrend.slice(-days).map((item) => {
    const dateObj = new Date(item.date);
    return {
      date: dateObj.toLocaleDateString("zh-CN", {
        month: "2-digit",
        day: "2-digit"
      }),
      dateStr: item.date, // 原始日期字符串 YYYY-MM-DD，直接使用
      total_count: item.total_count,
      success_count: item.success_count,
      failed_count: item.failed_count,
      success_rate: item.success_rate * 100 // 转换为百分比
    };
  });

  // 处理图表点击事件
  const handleChartClick = (data: any) => {
    if (!onDateClick || !data || !data.activePayload) return;
    // 从第一个 payload 中获取数据（所有系列共享同一个数据点）
    const clickedData = data.activePayload[0]?.payload;
    if (clickedData?.dateStr) {
      onDateClick(clickedData.dateStr);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col h-full">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">
          每日任务趋势
        </h3>
        <div className="flex items-center gap-4">
          {/* 自定义图例 - 右对齐 */}
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#c7d2fe]" />
              <span className="text-slate-600 font-medium">成功率</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#0ea5e9]" />
              <span className="text-slate-600 font-medium">总任务数</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#22c55e]" />
              <span className="text-slate-600 font-medium">成功任务数</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#ef4444]" />
              <span className="text-slate-600 font-medium">失败任务数</span>
            </div>
          </div>
          {showViewDetails && onViewDetails && (
            <button
              onClick={onViewDetails}
              className="text-sm text-sky-600 hover:text-sky-700 hover:underline transition-colors"
            >
              查看详情 →
            </button>
          )}
        </div>
      </div>
      <div className="mt-4 flex-1 min-h-[224px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={trendData} onClick={handleChartClick} style={{ cursor: onDateClick ? 'pointer' : 'default' }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" stroke="#94a3b8" />
            <YAxis yAxisId="left" stroke="#94a3b8" />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#94a3b8"
              unit="%"
              domain={[0, 100]}
            />
            <Tooltip
              content={({ payload, label }) => {
                if (!payload || payload.length === 0) return null;
                return (
                  <div className="rounded-lg border border-sky-100 bg-sky-50/90 backdrop-blur-sm p-3 shadow-md">
                    <p className="font-medium text-slate-900 mb-2">{label}</p>
                    <div className="space-y-1">
                      {payload.map((entry, index) => (
                        <div key={index} className="flex items-center justify-between gap-4">
                          <div className="flex items-center gap-2">
                            <span
                              className="inline-block h-3 w-3 rounded-sm"
                              style={{ backgroundColor: entry.color ?? '#94a3b8' }}
                            />
                            <span className="text-xs text-slate-600">{entry.name ?? '未知'}</span>
                          </div>
                          <span className="text-sm font-semibold text-slate-900">
                            {entry.name === "成功率"
                              ? `${Number(entry.value ?? 0).toFixed(1)}%`
                              : entry.value ?? 0}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }}
            />
            <Bar
              yAxisId="right"
              dataKey="success_rate"
              name="成功率"
              fill="#c7d2fe"
              radius={[4, 4, 0, 0]}
              maxBarSize={30}
              legendType="square"
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="total_count"
              name="总任务数"
              stroke="#0ea5e9"
              strokeWidth={2}
              dot={{ r: 3, fill: "#0ea5e9" }}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="success_count"
              name="成功任务数"
              stroke="#22c55e"
              strokeWidth={2}
              dot={{ r: 3, fill: "#22c55e" }}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="failed_count"
              name="失败任务数"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ r: 3, fill: "#ef4444" }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}


