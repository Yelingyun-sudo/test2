import type { LLMUsage, PaginatedListResponse } from "./common";

// 、对应数据库中的一条取证任务记录，也是列表页展示的一行数据。
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

// 定义单个取证条目的细节。
export type EvidenceEntryDetail = {
  json: string;
  // 截图文件路径
  screenshot: string;
  text: string;
};

// 定义任务产出的文件资源清单。
export type TaskArtifacts = {
  register_image_path: string | null;
  login_image_path: string | null;
  evidence_image_path: string | null;
  evidence_entries_detail?: EvidenceEntryDetail[] | null;
  video_path: string | null;
  video_seek_seconds: number | null;
};

export type ArtifactUrls = {
  registerImageUrl: string | null;
  loginImageUrl: string | null;
  evidenceImageUrl: string | null;
  videoUrl: string | null;
};

export type MediaFlags = {
  login: boolean;
  evidence: boolean;
};

export type EvidenceListResponse = PaginatedListResponse<EvidenceItem>;
