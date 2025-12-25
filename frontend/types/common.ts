export type LLMUsage = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  llm_turns: number;
  total_cached_tokens?: number;
  total_reasoning_tokens?: number;
};

export type TaskStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED";

export const STATUS_LABELS: Record<TaskStatus, string> = {
  PENDING: "待执行",
  RUNNING: "执行中",
  SUCCESS: "成功",
  FAILED: "失败"
};

export const STATUS_STYLES: Record<TaskStatus, string> = {
  PENDING: "bg-slate-100 text-slate-600 border border-slate-200",
  RUNNING: "bg-yellow-100 text-yellow-700 border border-yellow-200",
  SUCCESS: "bg-emerald-50 text-emerald-600 border border-emerald-100",
  FAILED: "bg-rose-50 text-rose-600 border border-rose-100"
};

export const STATUS_COLORS: Record<TaskStatus, string> = {
  PENDING: "#94a3b8",
  RUNNING: "#facc15",
  SUCCESS: "#22c55e",
  FAILED: "#ef4444"
};

export type PaginatedListResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

