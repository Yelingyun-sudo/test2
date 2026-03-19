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

/**
 * 复制文本到剪贴板（包含降级方案）
 * @param text - 要复制的文本
 * @returns Promise<boolean> - 是否复制成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 方案1：优先使用现代 Clipboard API（需要 HTTPS 或 localhost）
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // Clipboard API 失败，继续尝试降级方案
      console.warn("Clipboard API failed, trying fallback:", err);
    }
  }

  // 方案2：降级方案 - 使用传统的 execCommand 方法
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.left = "-999999px";
    textarea.style.top = "-999999px";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    const successful = document.execCommand("copy");
    document.body.removeChild(textarea);

    if (successful) {
      return true;
    }
  } catch (err) {
    console.error("Fallback copy method failed:", err);
  }

  return false;
}
