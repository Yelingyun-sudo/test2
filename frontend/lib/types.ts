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
  status: string;
  count: number;
}

export interface RecentTaskItem {
  id: number;
  url: string;
  status: string;
  executed_at: string | null;
  duration_seconds: number | null;
  result: string | null;
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
  recent_tasks: RecentTaskItem[];
  failure_type_distribution: FailureTypeDistributionItem[];
  failure_summary: FailureSummary;
}
