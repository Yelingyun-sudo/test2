"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Pause, Play, RotateCcw, Copy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatDurationSeconds, parseDateTime } from "@/lib/datetime";
import { cn, copyToClipboard } from "@/lib/utils";
import type { SubscriptionItem, TaskArtifacts, ArtifactUrls, MediaFlags } from "@/types/subscription";
import {
  STATUS_LABELS,
  STATUS_STYLES,
  type TaskStatus,
} from "@/types/common";

type TaskDetailModalProps = {
  task: SubscriptionItem;
  onClose: () => void;
  failureTypeLabel: Record<string, string>;
};

function MediaLoadingOverlay({ label }: { label: string }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white/75 backdrop-blur-sm">
      <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function shellQuoteSingle(value: string): string {
  return `'${value.replace(/'/g, `'\\\\''`)}'`;
}

function buildReplayInstruction(item: SubscriptionItem): string {
  const url = (item.url ?? "").trim();
  const account = (item.account ?? "").trim();
  const password = (item.password ?? "").trim();
  return `登录 ${url}（账号和密码分别为 ${account} 和 ${password}）并提取订阅地址`;
}

function buildReplayCommand(item: SubscriptionItem): string {
  return `uv run python -m website_analytics.main --instruction ${shellQuoteSingle(
    buildReplayInstruction(item)
  )}`;
}

function formatNumber(num: number | undefined): string {
  if (num === undefined || num === null) return "0";
  return num.toLocaleString("zh-CN");
}

export function TaskDetailModal({ task, onClose, failureTypeLabel }: TaskDetailModalProps) {
  const [artifacts, setArtifacts] = useState<TaskArtifacts | null>(null);
  const [artifactUrls, setArtifactUrls] = useState<ArtifactUrls>({
    loginImageUrl: null,
    extractImageUrl: null,
    videoUrl: null
  });
  const [artifactsLoading, setArtifactsLoading] = useState(false);
  const [mediaReady, setMediaReady] = useState<MediaFlags>({
    login: false,
    extract: false
  });
  const [mediaError, setMediaError] = useState<MediaFlags>({
    login: false,
    extract: false
  });

  // Viewer 核心状态
  const [viewer, setViewer] = useState<{
    type: "image" | "video";
    title: string;
    src: string | null;
    seekSeconds?: number | null;
  } | null>(null);

  // 视频播放状态
  const [viewerVideoState, setViewerVideoState] = useState({
    paused: true,
    ended: false
  });

  const [viewerPlayback, setViewerPlayback] = useState({
    duration: 0,
    currentTime: 0,
    dragging: false,
    dragValue: 0
  });

  // 视频加载状态
  const [videoBlobStatus, setVideoBlobStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [viewerVideoFetch, setViewerVideoFetch] = useState({
    loading: false,
    error: false,
    ready: false
  });

  const artifactUrlsRef = useRef<ArtifactUrls>({
    loginImageUrl: null,
    extractImageUrl: null,
    videoUrl: null
  });
  const artifactsControllerRef = useRef<AbortController | null>(null);
  const viewerVideoRef = useRef<HTMLVideoElement | null>(null);
  const videoBlobPromiseRef = useRef<Promise<string | null> | null>(null);

  const handleCopyReplayCommand = useCallback(async () => {
    const url = (task.url ?? "").trim();
    const account = (task.account ?? "").trim();
    const password = (task.password ?? "").trim();
    if (!url || !account || !password) {
      toast.error("缺少网址/用户名/密码，无法生成命令");
      return;
    }

    const success = await copyToClipboard(buildReplayCommand(task));
    if (success) {
      toast.success("复制成功");
    } else {
      toast.error("复制失败，请手动复制");
    }
  }, [task]);

  const handleCopyUrl = useCallback(async () => {
    const url = (task.url ?? "").trim();
    if (!url) {
      toast.error("网址为空，无法复制");
      return;
    }

    const success = await copyToClipboard(url);
    if (success) {
      toast.success("复制成功");
    } else {
      toast.error("复制失败，请手动复制");
    }
  }, [task.url]);

  const revokeArtifactUrls = useCallback((urls: ArtifactUrls) => {
    for (const value of Object.values(urls)) {
      if (value) URL.revokeObjectURL(value);
    }
  }, []);

  const fetchArtifactBlobUrl = useCallback(
    async (taskId: number, path: string | null, signal?: AbortSignal): Promise<string | null> => {
      if (!path) return null;
      const res = await apiFetch(
        `/subscription/${taskId}/artifact?path=${encodeURIComponent(path)}`,
        signal ? { signal } : undefined
      );
      if (!res.ok) return null;
      const blob = await res.blob();
      return URL.createObjectURL(blob);
    },
    []
  );

  const ensureVideoBlobUrl = useCallback(
    async (taskId: number, videoPath: string | null, signal?: AbortSignal): Promise<string | null> => {
      if (!videoPath) return null;
      const existing = artifactUrlsRef.current.videoUrl;
      if (existing) {
        setVideoBlobStatus("ready");
        return existing;
      }

      if (videoBlobPromiseRef.current) return videoBlobPromiseRef.current;
      setVideoBlobStatus("loading");

      const promise = fetchArtifactBlobUrl(taskId, videoPath, signal)
        .then((videoUrl) => {
          if (!videoUrl) {
            if (!signal?.aborted) setVideoBlobStatus("error");
            return null;
          }

          if (signal?.aborted) {
            URL.revokeObjectURL(videoUrl);
            return null;
          }

          const nextUrls: ArtifactUrls = { ...artifactUrlsRef.current, videoUrl };
          artifactUrlsRef.current = nextUrls;
          setArtifactUrls(nextUrls);
          setVideoBlobStatus("ready");
          return videoUrl;
        })
        .catch((error) => {
          const err = error as { name?: string };
          if (err?.name === "AbortError") return null;
          console.error(error);
          if (!signal?.aborted) setVideoBlobStatus("error");
          return null;
        })
        .finally(() => {
          if (videoBlobPromiseRef.current === promise) videoBlobPromiseRef.current = null;
        });

      videoBlobPromiseRef.current = promise;
      return promise;
    },
    [fetchArtifactBlobUrl]
  );

  const getWaitSeconds = (item: SubscriptionItem) => {
    const createdAt = parseDateTime(item.created_at);
    const executedAt = parseDateTime(item.executed_at);
    if (!createdAt || !executedAt) return null;
    return (executedAt.getTime() - createdAt.getTime()) / 1000;
  };

  const formatTaskDuration = (durationSeconds: number, status?: string) => {
    if (status === "PENDING" || status === "RUNNING" || status === "RETRYING") {
      return "-";
    }
    return formatDurationSeconds(durationSeconds);
  };

  // 辅助方法
  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

  const getViewerBaselineSeconds = () => {
    const raw = viewer?.seekSeconds;
    if (typeof raw !== "number" || Number.isNaN(raw) || raw <= 0) return 0;
    return raw;
  };

  const formatClock = (seconds: number) => {
    const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
    const whole = Math.floor(safe);
    const minutes = Math.floor(whole / 60);
    const remainder = whole % 60;
    return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  };

  // 视频事件处理
  const handleViewerVideoLoadedMetadata = () => {
    if (!viewerVideoRef.current) return;
    const duration = viewerVideoRef.current.duration;
    const hasDuration = typeof duration === "number" && Number.isFinite(duration) && duration > 0;
    const baseline = getViewerBaselineSeconds();
    const safeBaseline = hasDuration ? Math.min(baseline, Math.max(0, duration - 0.1)) : baseline;

    if (safeBaseline > 0) viewerVideoRef.current.currentTime = safeBaseline;
    viewerVideoRef.current.defaultPlaybackRate = 3;
    viewerVideoRef.current.playbackRate = 3;

    setViewerPlayback((prev) => ({
      ...prev,
      duration: hasDuration ? duration : 0,
      currentTime: viewerVideoRef.current?.currentTime ?? 0,
      dragValue: 0
    }));
  };

  const handleViewerTimeUpdate = () => {
    if (!viewerVideoRef.current) return;
    setViewerPlayback((prev) => {
      if (prev.dragging) return prev;
      return { ...prev, currentTime: viewerVideoRef.current?.currentTime ?? 0 };
    });
  };

  const handleViewerTogglePlay = async () => {
    if (!viewerVideoRef.current) return;
    const baseline = getViewerBaselineSeconds();

    if (baseline > 0 && viewerVideoRef.current.currentTime < baseline) {
      viewerVideoRef.current.currentTime = baseline;
    }
    if (viewerVideoState.ended) {
      viewerVideoRef.current.currentTime = baseline;
    }

    viewerVideoRef.current.defaultPlaybackRate = 3;
    viewerVideoRef.current.playbackRate = 3;

    if (viewerVideoState.paused || viewerVideoState.ended) {
      try {
        await viewerVideoRef.current.play();
      } catch (error) {
        console.error(error);
      }
    } else {
      viewerVideoRef.current.pause();
    }
  };

  const handleViewerPlayOverlayClick = async () => {
    if (!viewerVideoRef.current) return;
    const baseline = getViewerBaselineSeconds();

    if (baseline > 0 && viewerVideoRef.current.currentTime < baseline) {
      viewerVideoRef.current.currentTime = baseline;
    }
    if (viewerVideoState.ended) {
      const duration = viewerVideoRef.current.duration;
      const hasDuration = typeof duration === "number" && Number.isFinite(duration) && duration > 0;
      const seekSeconds = viewer?.seekSeconds;
      const canSeek = typeof seekSeconds === "number" && !Number.isNaN(seekSeconds) && seekSeconds > 0;
      const target = canSeek
        ? hasDuration ? Math.min(seekSeconds, Math.max(0, duration - 0.1)) : seekSeconds
        : 0;
      viewerVideoRef.current.currentTime = target;
    }

    viewerVideoRef.current.defaultPlaybackRate = 3;
    viewerVideoRef.current.playbackRate = 3;

    try {
      await viewerVideoRef.current.play();
    } catch (error) {
      console.error(error);
    }
  };

  // 进度条控制
  const handleViewerSeekStart = () => {
    const baseline = getViewerBaselineSeconds();
    setViewerPlayback((prev) => {
      const visibleDuration = Math.max(prev.duration - baseline, 0);
      const currentDisplay = clamp(prev.currentTime - baseline, 0, visibleDuration);
      return { ...prev, dragging: true, dragValue: currentDisplay };
    });
  };

  const handleViewerSeekChange = (value: number) => {
    setViewerPlayback((prev) => ({ ...prev, dragValue: value }));
  };

  const handleViewerSeekEnd = () => {
    const baseline = getViewerBaselineSeconds();
    if (!viewerVideoRef.current) return;
    setViewerPlayback((prev) => {
      const visibleDuration = Math.max(prev.duration - baseline, 0);
      const displayValue = clamp(prev.dragValue, 0, visibleDuration);
      const target = baseline + displayValue;
      viewerVideoRef.current!.currentTime = target;
      return { ...prev, dragging: false, currentTime: target, dragValue: displayValue };
    });
  };

  useEffect(() => {
    if (!task) {
      revokeArtifactUrls(artifactUrlsRef.current);
      artifactUrlsRef.current = {
        loginImageUrl: null,
        extractImageUrl: null,
        videoUrl: null
      };
      setArtifactUrls(artifactUrlsRef.current);
      setArtifacts(null);
      setArtifactsLoading(false);
      artifactsControllerRef.current?.abort();
      artifactsControllerRef.current = null;
      return;
    }

    revokeArtifactUrls(artifactUrlsRef.current);
    artifactUrlsRef.current = {
      loginImageUrl: null,
      extractImageUrl: null,
      videoUrl: null
    };
    setArtifactUrls(artifactUrlsRef.current);
    setArtifacts(null);

    if (task.status === "PENDING" || task.status === "RUNNING" || task.status === "RETRYING") {
      setArtifacts({
        status: task.status,
        login_image_path: null,
        extract_image_path: null,
        video_path: null,
        video_seek_seconds: null
      });
      return;
    }

    const controller = new AbortController();
    artifactsControllerRef.current?.abort();
    artifactsControllerRef.current = controller;
    let cancelled = false;

    const load = async () => {
      setArtifactsLoading(true);
      try {
        const res = await apiFetch(`/subscription/${task.id}/artifacts`, {
          signal: controller.signal
        });
        if (!res.ok) throw new Error("加载任务产物失败");
        const payload = (await res.json()) as TaskArtifacts;
        if (cancelled) return;
        setArtifacts(payload);

        const [loginImageUrl, extractImageUrl] = await Promise.all([
          fetchArtifactBlobUrl(task.id, payload.login_image_path, controller.signal),
          fetchArtifactBlobUrl(task.id, payload.extract_image_path, controller.signal)
        ]);

        if (cancelled) {
          revokeArtifactUrls({ loginImageUrl, extractImageUrl, videoUrl: null });
          return;
        }

        setMediaReady({ login: false, extract: false });
        setMediaError({ login: false, extract: false });
        artifactUrlsRef.current = { loginImageUrl, extractImageUrl, videoUrl: null };
        setArtifactUrls(artifactUrlsRef.current);
      } finally {
        if (!cancelled) setArtifactsLoading(false);
      }
    };

    load().catch((error) => {
      console.error(error);
      if (!cancelled) setArtifactsLoading(false);
    });

    return () => {
      cancelled = true;
      controller.abort();
      revokeArtifactUrls(artifactUrlsRef.current);
      artifactUrlsRef.current = {
        loginImageUrl: null,
        extractImageUrl: null,
        videoUrl: null
      };
      artifactsControllerRef.current = null;
    };
  }, [fetchArtifactBlobUrl, revokeArtifactUrls, task]);

  useEffect(() => {
    if (!task) return;
    setMediaReady({ login: false, extract: false });
    setMediaError({ login: false, extract: false });
  }, [task]);

  // ESC 键关闭 viewer
  useEffect(() => {
    if (!viewer) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setViewer(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [viewer]);

  // Viewer 状态重置
  useEffect(() => {
    if (!viewer || viewer.type !== "video") return;
    setViewerVideoFetch({ loading: false, error: false, ready: false });
    setViewerVideoState({ paused: true, ended: false });
    setViewerPlayback({
      duration: 0,
      currentTime: 0,
      dragging: false,
      dragValue: 0
    });
  }, [viewer]);

  if (!task) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-6xl rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="订阅链接任务详情"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-slate-900">订阅链接任务详情</h3>
            <p className="text-sm text-slate-500">ID: {task.id ?? "-"}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleCopyReplayCommand}>
              复制重跑命令
            </Button>
            <Button variant="outline" size="sm" onClick={onClose}>
              关闭
            </Button>
          </div>
        </div>

        <div className="grid gap-4 px-6 py-5 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1">
            <div className="text-slate-500">网址</div>
            {task.url ? (
              <div className="flex items-center gap-2">
                <a
                  href={task.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all font-medium text-slate-800 hover:text-sky-600 hover:underline cursor-pointer transition-colors flex-1"
                >
                  {task.url}
                </a>
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 flex-shrink-0"
                        onClick={handleCopyUrl}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>复制网址</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            ) : (
              <div className="break-all font-medium text-slate-800">-</div>
            )}
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">用户名</div>
            <div className="break-all font-medium text-slate-800">{task.account}</div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">密码</div>
            <div className="break-all font-medium text-slate-800">{task.password}</div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">任务状态</div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium",
                  STATUS_STYLES[task.status as TaskStatus] || "bg-slate-100 text-slate-600 border border-slate-200"
                )}
              >
                {task.status === "RUNNING" && (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                )}
                {STATUS_LABELS[task.status as TaskStatus] || task.status}
              </span>
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">任务创建时间</div>
            <div className="font-medium">{formatDateTime(task.created_at)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">任务执行时间</div>
            <div className="font-medium">{formatDateTime(task.executed_at)}</div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">任务等待时间</div>
            <div className="font-medium">{formatDurationSeconds(getWaitSeconds(task))}</div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-500">任务时长 (s)</div>
            <div className="font-medium">{formatTaskDuration(task.duration_seconds, task.status)}</div>
          </div>
          {task.llm_usage && (
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="space-y-1 cursor-help">
                    <div className="text-slate-500">Token 使用</div>
                    <div className="font-medium text-blue-600 underline decoration-dashed decoration-slate-300 underline-offset-2">
                      🤖 {formatNumber(task.llm_usage.total_tokens)}
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  align="center"
                  className="w-64 p-4 bg-sky-50/95 backdrop-blur-sm border border-sky-100 shadow-md"
                >
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 border-b border-sky-200 pb-2">
                      <span className="text-sm font-semibold text-slate-900">📊 Token 使用详情</span>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-600">输入 Token</span>
                        <span className="font-mono text-blue-600">
                          {formatNumber(task.llm_usage.total_input_tokens)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">输出 Token</span>
                        <span className="font-mono text-green-600">
                          {formatNumber(task.llm_usage.total_output_tokens)}
                        </span>
                      </div>
                      <div className="flex justify-between border-t border-sky-200 pt-2">
                        <span className="font-medium text-slate-900">总计</span>
                        <span className="font-mono font-bold text-slate-900">
                          {formatNumber(task.llm_usage.total_tokens)}
                        </span>
                      </div>
                    </div>

                    {(task.llm_usage.total_cached_tokens ||
                      task.llm_usage.total_reasoning_tokens) && (
                      <div className="space-y-2 border-t border-sky-200 pt-2 text-xs">
                        {task.llm_usage.total_cached_tokens && (
                          <div className="flex justify-between">
                            <span className="text-slate-600">缓存优化</span>
                            <span className="font-mono text-orange-600">
                              {formatNumber(task.llm_usage.total_cached_tokens)}
                            </span>
                          </div>
                        )}
                        {task.llm_usage.total_reasoning_tokens && (
                          <div className="flex justify-between">
                            <span className="text-slate-600">推理 Token</span>
                            <span className="font-mono text-purple-600">
                              {formatNumber(task.llm_usage.total_reasoning_tokens)}
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex justify-between border-t border-sky-200 pt-2 text-xs">
                      <span className="text-slate-600">LLM 调用轮次</span>
                      <span className="font-mono text-cyan-600">
                        {task.llm_usage.llm_turns} 次
                      </span>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>

        <div className="px-6 pb-6">
          <div className="mb-2 flex items-center gap-2">
            <div className="text-sm font-semibold text-slate-700">任务结果</div>
            {(task.status === "FAILED" || task.status === "RETRYING") && task.failure_type && (
              <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10">
                {failureTypeLabel[task.failure_type] || task.failure_type}
              </span>
            )}
          </div>
          <Input
            readOnly
            value={(task.result ?? "").replace(/\s+/g, " ").trim()}
            placeholder="暂无结果"
            className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm text-slate-800 shadow-inner focus:outline-none"
          />
        </div>

        <div className="px-6 pb-6">
          <div className="mb-2 flex items-baseline gap-2 text-sm font-semibold text-slate-700">
            <span>任务日志</span>
            {task.task_dir && (
              <span className="font-mono text-xs text-slate-500">
                ({task.task_dir.split("/").pop() || task.task_dir})
              </span>
            )}
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-800">登录截图</div>
              </div>
              {artifactsLoading ? (
                <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                  <div className="absolute inset-0 animate-pulse bg-slate-100/70" />
                  <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white/75 backdrop-blur-sm">
                    <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
                    <div className="text-xs text-slate-500">加载中...</div>
                  </div>
                </div>
              ) : artifactUrls.loginImageUrl ? (
                <button
                  type="button"
                  className="group relative block w-full"
                  onClick={() => {
                    const src = artifactUrls.loginImageUrl;
                    if (!src) return;
                    setViewer({
                      type: "image",
                      title: "登录截图",
                      src
                    });
                  }}
                >
                  {!mediaReady.login && !mediaError.login ? (
                    <MediaLoadingOverlay label="加载中..." />
                  ) : null}
                  {mediaError.login ? (
                    <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                      加载失败
                    </div>
                  ) : null}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={artifactUrls.loginImageUrl}
                    alt="登录截图"
                    className={cn(
                      "w-full aspect-[16/10] rounded-xl border border-slate-200 object-contain bg-slate-50 cursor-zoom-in group-hover:shadow-sm transition-opacity",
                      mediaReady.login && !mediaError.login ? "opacity-100" : "opacity-0"
                    )}
                    onLoad={() => setMediaReady((prev) => ({ ...prev, login: true }))}
                    onError={() => setMediaError((prev) => ({ ...prev, login: true }))}
                  />
                </button>
              ) : (
                <div className="flex w-full aspect-[16/10] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                  不存在
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-800">提取截图</div>
              </div>
              {artifactsLoading ? (
                <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                  <div className="absolute inset-0 animate-pulse bg-slate-100/70" />
                  <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white/75 backdrop-blur-sm">
                    <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
                    <div className="text-xs text-slate-500">加载中...</div>
                  </div>
                </div>
              ) : artifactUrls.extractImageUrl ? (
                <button
                  type="button"
                  className="group relative block w-full"
                  onClick={() => {
                    const src = artifactUrls.extractImageUrl;
                    if (!src) return;
                    setViewer({
                      type: "image",
                      title: "提取截图",
                      src
                    });
                  }}
                >
                  {!mediaReady.extract && !mediaError.extract ? (
                    <MediaLoadingOverlay label="加载中..." />
                  ) : null}
                  {mediaError.extract ? (
                    <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                      加载失败
                    </div>
                  ) : null}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={artifactUrls.extractImageUrl}
                    alt="提取截图"
                    className={cn(
                      "w-full aspect-[16/10] rounded-xl border border-slate-200 object-contain bg-slate-50 cursor-zoom-in group-hover:shadow-sm transition-opacity",
                      mediaReady.extract && !mediaError.extract ? "opacity-100" : "opacity-0"
                    )}
                    onLoad={() => setMediaReady((prev) => ({ ...prev, extract: true }))}
                    onError={() => setMediaError((prev) => ({ ...prev, extract: true }))}
                  />
                </button>
              ) : (
                <div className="flex w-full aspect-[16/10] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                  不存在
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-baseline gap-2">
                  <div className="text-sm font-semibold text-slate-800">操作视频</div>
                  {artifacts?.video_seek_seconds ? (
                    <div className="text-xs text-slate-500">
                      建议从 {artifacts.video_seek_seconds}s 开始播放(x3倍速)
                    </div>
                  ) : null}
                </div>
              </div>
              {artifactsLoading ? (
                <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                  <div className="absolute inset-0 animate-pulse bg-slate-100/70" />
                  <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white/75 backdrop-blur-sm">
                    <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
                    <div className="text-xs text-slate-500">加载中...</div>
                  </div>
                </div>
              ) : artifacts?.video_path ? (
                <button
                  type="button"
                  className="group relative block w-full"
                  onClick={async () => {
                    if (!task) return;
                    const videoPath = artifacts?.video_path;
                    if (!videoPath) return;

                    const existing = artifactUrlsRef.current.videoUrl;
                    setViewer({
                      type: "video",
                      title: "操作视频",
                      src: existing,
                      seekSeconds: artifacts?.video_seek_seconds ?? null
                    });

                    if (existing) return;

                    setViewerVideoFetch({ loading: true, error: false, ready: false });
                    const videoUrl = await ensureVideoBlobUrl(
                      task.id,
                      videoPath,
                      artifactsControllerRef.current?.signal
                    );
                    if (!videoUrl) {
                      setViewerVideoFetch({ loading: false, error: true, ready: false });
                      return;
                    }
                    setViewer((prev) =>
                      prev && prev.type === "video"
                        ? { ...prev, src: videoUrl }
                        : prev
                    );
                  }}
                  aria-label="播放操作视频"
                >
                  {artifactUrls.loginImageUrl && !mediaError.login ? (
                    <>
                      {!mediaReady.login ? <MediaLoadingOverlay label="加载中..." /> : null}
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={artifactUrls.loginImageUrl}
                        alt="操作视频封面"
                        className={cn(
                          "w-full aspect-[16/10] rounded-xl border border-slate-200 object-contain bg-slate-50 transition-opacity",
                          mediaReady.login && !mediaError.login ? "opacity-100" : "opacity-0"
                        )}
                        onLoad={() => setMediaReady((prev) => ({ ...prev, login: true }))}
                        onError={() => setMediaError((prev) => ({ ...prev, login: true }))}
                      />
                    </>
                  ) : (
                    <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                      <div className="absolute inset-0 bg-slate-100/60" />
                    </div>
                  )}
                  <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/60 bg-black/40 backdrop-blur-sm transition group-hover:scale-105 group-hover:bg-black/55">
                      <Play className="h-7 w-7 translate-x-[1px] text-white" fill="currentColor" />
                    </div>
                  </div>
                </button>
              ) : (
                <div className="flex w-full aspect-[16/10] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                  不存在
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Viewer 弹窗（图片/视频查看器）*/}
      {viewer && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-white/90 p-4 backdrop-blur-sm"
          onClick={() => setViewer(null)}
          role="dialog"
          aria-modal="true"
          aria-label={`${viewer.title}预览`}
        >
          <div
            className="w-full max-w-6xl rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div className="text-sm font-semibold text-slate-900">{viewer.title}</div>
              <Button variant="outline" size="sm" onClick={() => setViewer(null)}>
                关闭
              </Button>
            </div>
            <div className="p-4">
              {viewer.type === "image" ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={viewer.src ?? ""}
                  alt={viewer.title}
                  className="max-h-[80vh] w-full rounded-xl bg-white object-contain"
                />
              ) : (
                <div className="relative">
                  {/* 视频容器 */}
                  <div className="relative w-full aspect-[16/10] max-h-[80vh] overflow-hidden rounded-xl bg-black">
                    {/* 加载状态覆盖层 */}
                    {viewerVideoFetch.loading || (!viewerVideoFetch.ready && !viewerVideoFetch.error) ? (
                      <div className="absolute inset-0 z-20">
                        <MediaLoadingOverlay label={videoBlobStatus === "loading" ? "加载视频中..." : "加载中..."} />
                      </div>
                    ) : null}

                    {/* 错误状态覆盖层 */}
                    {viewerVideoFetch.error ? (
                      <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                        加载失败
                      </div>
                    ) : null}

                    {/* 视频元素 */}
                    {viewer.src ? (
                      <video
                        ref={viewerVideoRef}
                        className="h-full w-full bg-black object-contain"
                        controls={false}
                        autoPlay
                        preload="metadata"
                        src={viewer.src}
                        onLoadedMetadata={handleViewerVideoLoadedMetadata}
                        onLoadedData={() =>
                          setViewerVideoFetch((prev) => ({ ...prev, loading: false, error: false, ready: true }))
                        }
                        onError={() => setViewerVideoFetch({ loading: false, error: true, ready: false })}
                        onPlay={() => {
                          if (viewerVideoRef.current) {
                            viewerVideoRef.current.defaultPlaybackRate = 3;
                            viewerVideoRef.current.playbackRate = 3;
                          }
                          setViewerVideoState({ paused: false, ended: false });
                        }}
                        onPause={() => setViewerVideoState((prev) => ({ ...prev, paused: true }))}
                        onEnded={() => setViewerVideoState({ paused: true, ended: true })}
                        onTimeUpdate={handleViewerTimeUpdate}
                      />
                    ) : (
                      <div className="h-full w-full" />
                    )}
                  </div>

                  {/* 大播放按钮覆盖 */}
                  {(viewerVideoState.paused || viewerVideoState.ended) &&
                    viewerVideoFetch.ready &&
                    !viewerVideoFetch.error && (
                    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                      <button
                        type="button"
                        className="pointer-events-auto flex h-16 w-16 items-center justify-center rounded-full border border-white/60 bg-black/40 backdrop-blur-sm transition hover:scale-105 hover:bg-black/55"
                        onClick={handleViewerPlayOverlayClick}
                        aria-label={viewerVideoState.ended ? "重播视频" : "播放视频"}
                      >
                        {viewerVideoState.ended ? (
                          <RotateCcw className="h-7 w-7 text-white" />
                        ) : (
                          <Play className="h-8 w-8 translate-x-[1px] text-white" fill="currentColor" />
                        )}
                      </button>
                    </div>
                  )}

                  {/* 控制条 */}
                  {(() => {
                    const baseline = getViewerBaselineSeconds();
                    const visibleDuration = Math.max(viewerPlayback.duration - baseline, 0);
                    const displayCurrent = viewerPlayback.dragging
                      ? viewerPlayback.dragValue
                      : clamp(viewerPlayback.currentTime - baseline, 0, visibleDuration);
                    const disabled = !Number.isFinite(visibleDuration) || visibleDuration <= 0;

                    return (
                      <div className="mt-3 flex items-center gap-3 rounded-xl border border-slate-200 bg-white/90 px-3 py-2">
                        <button
                          type="button"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                          onClick={handleViewerTogglePlay}
                          aria-label={viewerVideoState.ended ? "重播" : viewerVideoState.paused ? "播放" : "暂停"}
                        >
                          {viewerVideoState.ended ? (
                            <RotateCcw className="h-4 w-4" />
                          ) : viewerVideoState.paused ? (
                            <Play className="h-4 w-4 translate-x-[1px]" />
                          ) : (
                            <Pause className="h-4 w-4" />
                          )}
                        </button>

                        <input
                          type="range"
                          min={0}
                          max={visibleDuration}
                          step={0.1}
                          value={disabled ? 0 : displayCurrent}
                          disabled={disabled}
                          className="flex-1"
                          onPointerDown={handleViewerSeekStart}
                          onPointerUp={handleViewerSeekEnd}
                          onPointerCancel={handleViewerSeekEnd}
                          onChange={(e) => handleViewerSeekChange(Number(e.target.value))}
                        />

                        <div className="whitespace-nowrap text-xs tabular-nums text-slate-600">
                          {formatClock(displayCurrent)} / {formatClock(visibleDuration)}
                          <span className="ml-2 text-slate-500">3x</span>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
