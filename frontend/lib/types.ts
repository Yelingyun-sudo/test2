import type { TaskStatus } from "@/types/common";
import type { SubscriptionItem } from "@/types/subscription";

export interface StatsSummary {
  total_tasks: number;
  today_tasks: number;
  success_count: number;
  failed_count: number;
  pending_count: number;
  running_count: number;
  success_rate: number;
  avg_success_duration_seconds: number;
  avg_failed_duration_seconds: number;
  total_tokens: number;
  today_tokens: number;
  avg_success_tokens: number;
  avg_failed_tokens: number;
  today_success_count: number;
  today_failed_count: number;
  today_success_rate: number;
  today_avg_success_duration_seconds: number;
  today_avg_failed_duration_seconds: number;
  today_avg_success_tokens: number;
  today_avg_failed_tokens: number;
}

export interface DailyTrendItem {
  date: string;
  total_count: number;
  success_count: number;
  failed_count: number;
  success_rate: number;
}

export interface StatusDistributionItem {
  status: TaskStatus;
  count: number;
}

export interface FailureTypeDistributionItem {
  type: string;
  label: string;
  count: number;
  percentage: number;
}

export interface FailureSummary {
  total_failed: number;
  unique_types: number;
}

export interface StatsResponse {
  summary: StatsSummary;
  daily_trend: DailyTrendItem[];
  status_distribution: StatusDistributionItem[];
  recent_tasks: SubscriptionItem[];
  failure_type_distribution: FailureTypeDistributionItem[];
  failure_summary: FailureSummary;
}

// ===== 专用端点响应类型 =====

export interface SummaryResponse {
  summary: StatsSummary;
}

export interface DailyTrendResponse {
  daily_trend: DailyTrendItem[];
}

export interface StatusDistributionResponse {
  status_distribution: StatusDistributionItem[];
}

export interface RecentTasksResponse {
  recent_tasks: SubscriptionItem[];
}

export interface FailureTypesStatsResponse {
  failure_type_distribution: FailureTypeDistributionItem[];
  failure_summary: FailureSummary;
}

// ===== Evidence 统计类型 =====

export interface EvidenceStatsSummary {
  total_tasks: number;
  pending_count: number;
  running_count: number;
  today_success_count: number;
  today_failed_count: number;
  today_tokens: number;
  today_avg_success_tokens: number;
  today_avg_failed_tokens: number;
  today_avg_success_duration_seconds: number;
  today_avg_failed_duration_seconds: number;
}

export interface EvidenceStatsResponse {
  summary: EvidenceStatsSummary;
  daily_trend: DailyTrendItem[];
  status_distribution: StatusDistributionItem[];
  recent_tasks: import("@/types/evidence").EvidenceItem[];
  failure_type_distribution: FailureTypeDistributionItem[];
  failure_summary: FailureSummary;
}

// Evidence 专用端点响应类型

export interface EvidenceSummaryResponse {
  summary: EvidenceStatsSummary;
}

export interface EvidenceDailyTrendResponse {
  daily_trend: DailyTrendItem[];
}

export interface EvidenceStatusDistributionResponse {
  status_distribution: StatusDistributionItem[];
}

export interface EvidenceRecentTasksResponse {
  recent_tasks: import("@/types/evidence").EvidenceItem[];
}

export interface EvidenceFailureTypesStatsResponse {
  failure_type_distribution: FailureTypeDistributionItem[];
  failure_summary: FailureSummary;
}
