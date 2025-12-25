import type { LLMUsage, PaginatedListResponse } from "./common";

export type SubscriptionItem = {
  id: number;
  url: string;
  account: string;
  password: string;
  status: string;
  created_at?: string | null;
  duration_seconds: number;
  executed_at?: string | null;
  task_dir?: string | null;
  result?: string | null;
  failure_type?: string | null;
  llm_usage?: LLMUsage | null;
};

export type TaskArtifacts = {
  status: string;
  login_image_path: string | null;
  extract_image_path: string | null;
  video_path: string | null;
  video_seek_seconds: number | null;
};

export type ArtifactUrls = {
  loginImageUrl: string | null;
  extractImageUrl: string | null;
  videoUrl: string | null;
};

export type MediaFlags = {
  login: boolean;
  extract: boolean;
};

export type SubscriptionListResponse = PaginatedListResponse<SubscriptionItem>;

