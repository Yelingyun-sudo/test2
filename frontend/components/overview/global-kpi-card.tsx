"use client";

import { cn } from "@/lib/utils";

interface Breakdown {
  label: string;
  value: string | number;
  percentage?: number;
}

interface GlobalKPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  breakdown: Breakdown[];
  className?: string;
}

export function GlobalKPICard({
  title,
  value,
  unit,
  breakdown,
  className
}: GlobalKPICardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-gradient-to-br from-blue-50 to-cyan-50 border-blue-100 p-6 shadow-sm backdrop-blur",
        className
      )}
    >
      {/* 标题 */}
      <h3 className="text-sm font-medium text-slate-600 mb-3">{title}</h3>

      {/* 主要数值 */}
      <div className="flex items-baseline gap-2 mb-4">
        <span className="text-4xl font-bold text-slate-900">{value}</span>
        {unit && <span className="text-sm text-slate-600">{unit}</span>}
      </div>

      {/* 细分数据 */}
      <div className="space-y-2">
        {breakdown.map((item, index) => (
          <div
            key={index}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-slate-600">{item.label}:</span>
            <span className="font-medium text-slate-900">
              {item.value}
              {item.percentage !== undefined && (
                <span className="ml-1 text-xs text-slate-500">
                  ({item.percentage}%)
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
