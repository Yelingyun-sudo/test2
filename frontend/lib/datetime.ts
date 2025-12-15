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

