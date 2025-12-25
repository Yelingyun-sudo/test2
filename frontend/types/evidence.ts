import type { LLMUsage, PaginatedListResponse } from "./common";

export type EvidenceItem = {
  id: number;
  url: string;
  account: string | null;
  password: string | null;
  status: string;
  created_at: string;
  executed_at: string;
  duration_seconds: number;
  result: string | null;
  failure_type: string | null;
  task_dir: string | null;
  llm_usage?: LLMUsage | null;
};

export type TaskArtifacts = {
  login_image_path: string | null;
  evidence_image_path: string | null;
  video_path: string | null;
  video_seek_seconds: number | null;
};

export type ArtifactUrls = {
  loginImageUrl: string | null;
  evidenceImageUrl: string | null;
  videoUrl: string | null;
};

export type MediaFlags = {
  login: boolean;
  evidence: boolean;
};

export type EvidenceListResponse = PaginatedListResponse<EvidenceItem>;
