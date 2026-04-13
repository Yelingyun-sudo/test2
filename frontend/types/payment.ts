import type { LLMUsage, PaginatedListResponse } from "./common";

export type PaymentItem = {
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

export type PaymentArtifacts = {
  status: string;
  qr_code_image: string | null;
  login_image_path: string | null;
  video_path: string | null;
  video_seek_seconds: number | null;
  screenshot_1: string | null;
  screenshot_2: string | null;
  screenshot_3: string | null;
};

export type PaymentArtifactUrls = {
  qrCodeImageUrl: string | null;
  loginImageUrl: string | null;
  videoUrl: string | null;
  screenshot1Url: string | null;
  screenshot2Url: string | null;
  screenshot3Url: string | null;
};

export type PaymentMediaFlags = {
  qrCode: boolean;
  login: boolean;
  screenshot1: boolean;
  screenshot2: boolean;
  screenshot3: boolean;
};

export type PaymentListResponse = PaginatedListResponse<PaymentItem>;