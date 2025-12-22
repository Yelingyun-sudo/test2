import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 智能格式化 token 数量，使用 K/M/G 单位
 * @param value - token 数量
 * @returns 格式化后的字符串，例如 "12.5K", "1.2M", "1.5G"
 */
export function formatTokenCount(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return "-";

  const num = Math.max(0, value);

  if (num < 1000) {
    return num.toString();
  }

  if (num < 1_000_000) {
    // K (千)
    const k = num / 1000;
    return Number.isInteger(k) ? `${k}K` : `${k.toFixed(1)}K`;
  }

  if (num < 1_000_000_000) {
    // M (百万)
    const m = num / 1_000_000;
    return Number.isInteger(m) ? `${m}M` : `${m.toFixed(1)}M`;
  }

  // G (十亿)
  const g = num / 1_000_000_000;
  return Number.isInteger(g) ? `${g}G` : `${g.toFixed(1)}G`;
}
