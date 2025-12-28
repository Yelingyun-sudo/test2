"use client";

import {
  CartesianGrid,
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { DailyTrendItem } from "@/lib/types";

type DailyTrendStackedBarChartProps = {
  dailyTrend: DailyTrendItem[];
  days?: number;
  onDateClick?: (date: string) => void;
};

export function DailyTrendStackedBarChart({
  dailyTrend,
  days = 5,
  onDateClick
}: DailyTrendStackedBarChartProps) {
  // 处理图表数据：倒序（最新日期在最上面）
  const trendData = dailyTrend
    .slice(-days)
    .reverse()  // 倒序：最新日期在最上面
    .map((item) => {
      const dateObj = new Date(item.date);
      return {
        date: dateObj.toLocaleDateString("zh-CN", {
          month: "2-digit",
          day: "2-digit"
        }),
        dateStr: item.date, // 原始日期字符串 YYYY-MM-DD，用于点击事件
        total_count: item.total_count,
        success_count: item.success_count,
        failed_count: item.failed_count,
        success_rate: (item.success_rate * 100).toFixed(1) // 转换为百分比字符串
      };
    });

  // 处理图表点击事件
  const handleChartClick = (data: any) => {
    if (!onDateClick || !data) return;
    // 从 data 中获取原始日期
    const clickedData = data?.dateStr;
    if (clickedData) {
      onDateClick(clickedData);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col h-full">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">
          每日任务趋势
        </h3>
        {/* 图例 - 右上角 */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm bg-[#22c55e]" />
            <span className="text-slate-600 font-medium">成功</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm bg-[#ef4444]" />
            <span className="text-slate-600 font-medium">失败</span>
          </div>
        </div>
      </div>
      <div className="mt-4 flex-1 min-h-[224px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={trendData}
            onClick={(data) => {
              if (data?.activePayload?.[0]?.payload) {
                handleChartClick(data.activePayload[0].payload);
              }
            }}
            style={{ cursor: onDateClick ? 'pointer' : 'default' }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={true} />
            <XAxis type="number" stroke="#94a3b8" />
            <YAxis
              type="category"
              dataKey="date"
              stroke="#94a3b8"
              width={60}
              tick={{ fontSize: 12 }}
            />

            {/* 成功任务柱子（绿色）*/}
            <Bar
              dataKey="success_count"
              stackId="tasks"
              fill="#22c55e"
              radius={[0, 0, 0, 0]}  // 堆叠时不需要圆角
              maxBarSize={30}
              activeBar={false}
            />

            {/* 失败任务柱子（红色）- 带成功率标签 */}
            <Bar
              dataKey="failed_count"
              stackId="tasks"
              fill="#ef4444"
              radius={[0, 8, 8, 0]}  // 右侧圆角
              maxBarSize={30}
              activeBar={false}
              label={{
                position: 'right',
                formatter: (_value: number, entry: any) => {
                  if (!entry || typeof entry.success_rate === 'undefined') return '';
                  return `${entry.success_rate}%`;
                },
                fontSize: 12,
                fill: '#64748b'
              }}
            />

            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const data = payload[0].payload;
                return (
                  <div className="rounded-lg border border-sky-100 bg-sky-50/90 backdrop-blur-sm p-3 shadow-md">
                    <p className="font-medium text-slate-900 mb-2">{data.date}</p>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-xs text-slate-600">总任务数</span>
                        <span className="font-semibold text-slate-900">{data.total_count}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-xs text-green-600">成功</span>
                        <span className="font-semibold text-green-700">{data.success_count}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-xs text-red-600">失败</span>
                        <span className="font-semibold text-red-700">{data.failed_count}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-xs text-slate-600">成功率</span>
                        <span className="font-semibold text-sky-600">{data.success_rate}%</span>
                      </div>
                    </div>
                    {onDateClick && (
                      <p className="mt-2 text-xs text-sky-600">
                        点击查看详情 →
                      </p>
                    )}
                  </div>
                );
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
