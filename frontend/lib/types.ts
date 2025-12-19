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
  created_at: string | null;
  duration_seconds: number | null;
  result: string | null;
}

export interface StatsResponse {
  summary: StatsSummary;
  daily_trend: DailyTrendItem[];
  status_distribution: StatusDistributionItem[];
  recent_tasks: RecentTaskItem[];
}
