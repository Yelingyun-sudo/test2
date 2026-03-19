"use client";

export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const normalized = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)
    ? `${value}Z`
    : value;

  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return value;

  const formatter = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });

  const parts = formatter.formatToParts(d);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value ?? "";

  return `${pick("year")}-${pick("month")}-${pick("day")} ${pick("hour")}:${pick("minute")}:${pick("second")}`;
}

export function parseDateTime(value?: string | null): Date | null {
  if (!value) return null;
  const normalized = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)
    ? `${value}Z`
    : value;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

/**
 * 格式化时长（秒）为可读字符串
 * @param value 时长（秒），可为 null 或 undefined
 * @returns 格式化后的字符串，如 "2分30秒"、"1小时5分10秒"
 */
export function formatDurationSeconds(value?: number | null): string {
  if (value == null || isNaN(value)) return "-";
  const totalSeconds = Math.max(0, Math.floor(value));
  if (totalSeconds < 60) return `${totalSeconds}秒`;

  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (totalSeconds < 3600) return `${minutes}分${seconds}秒`;
  if (totalSeconds < 86_400)
    return `${hours}小时${minutes}分${seconds}秒`;
  return `${days}天${hours}小时${minutes}分${seconds}秒`;
}

