"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, Pause, Play, RotateCcw, Copy } from "lucide-react";
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
import { formatDateTime, parseDateTime } from "@/lib/datetime";
import { cn, copyToClipboard, formatTokenCount } from "@/lib/utils";
import type {
  EvidenceItem,
  TaskArtifacts,
  ArtifactUrls,
  MediaFlags,
} from "@/types/evidence";
import {
  STATUS_LABELS,
  STATUS_STYLES,
  type TaskStatus,
} from "@/types/common";

function shellQuoteSingle(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function buildReplayInstruction(item: EvidenceItem): string {
  const url = (item.url ?? "").trim();
  const account = (item.account ?? "").trim();
  const password = (item.password ?? "").trim();
  
  if (account && password) {
    return `登录 ${url}（账号和密码分别为 ${account} 和 ${password}）并完成取证`;
  } else {
    return `访问 ${url} 注册账号并登录，最终完成取证`;
  }
}

function buildReplayCommand(item: EvidenceItem): string {
  return `uv run python -m website_analytics.main --instruction ${shellQuoteSingle(
    buildReplayInstruction(item)
  )}`;
}

function MediaLoadingOverlay({ label }: { label: string }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white/75 backdrop-blur-sm">
      <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function formatNumber(num: number | undefined): string {
  if (num === undefined || num === null) return "0";
  return num.toLocaleString("zh-CN");
}

function extractEntryLabel(screenshotPath: string, keepExtension = false): string {
  // 从路径中提取中文名称，例如 "evidence/02_我的订单.png" -> "我的订单" 或 "我的订单.png"
  const fileName = screenshotPath.split("/").pop() || screenshotPath;
  // 去掉序号前缀（两位数字 + 下划线），例如 "02_我的订单.png" -> "我的订单.png"
  const withoutPrefix = fileName.replace(/^\d{2}_/, "");
  if (keepExtension) {
    return withoutPrefix;
  }
  // 去掉文件扩展名
  const withoutExt = withoutPrefix.replace(/\.[^.]+$/, "");
  return withoutExt;
}

type TaskDetailModalProps = {
  task: EvidenceItem;
  onClose: () => void;
  failureTypeLabel: Record<string, string>;
};

export function TaskDetailModal({ task, onClose, failureTypeLabel }: TaskDetailModalProps) {
  const [artifacts, setArtifacts] = useState<TaskArtifacts | null>(null);
  const [artifactUrls, setArtifactUrls] = useState<ArtifactUrls>({
    registerImageUrl: null,
    loginImageUrl: null,
    evidenceImageUrl: null,
    videoUrl: null
  });
  const [viewer, setViewer] = useState<{
    type: "image" | "video";
    title: string;
    src: string | null;
    seekSeconds?: number | null;
    evidenceEntries?: Array<{ screenshot: string; json: string; text: string }> | null;
    currentEvidenceIndex?: number;
    authEntries?: Array<{ type: 'register' | 'login'; url: string; label: string }> | null;
    currentAuthIndex?: number;
  } | null>(null);
  const [currentEvidenceIndex, setCurrentEvidenceIndex] = useState(0);
  const [currentAuthIndex, setCurrentAuthIndex] = useState(0);
  const [currentEvidenceImageUrl, setCurrentEvidenceImageUrl] = useState<string | null>(null);
  const [evidenceImageLoading, setEvidenceImageLoading] = useState(false);
  const [cardEvidenceIndex, setCardEvidenceIndex] = useState(0);
  const [cardEvidenceImageUrls, setCardEvidenceImageUrls] = useState<(string | null)[]>([]);
  const [cardEvidenceLoading, setCardEvidenceLoading] = useState(false);
  const [cardAuthIndex, setCardAuthIndex] = useState(0);
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
  const [artifactsLoading, setArtifactsLoading] = useState(false);
  const [mediaReady, setMediaReady] = useState<MediaFlags>({
    login: false,
    evidence: false
  });
  const [mediaError, setMediaError] = useState<MediaFlags>({
    login: false,
    evidence: false
  });
  const [viewerVideoFetch, setViewerVideoFetch] = useState({ loading: false, error: false, ready: false });
  const [videoBlobStatus, setVideoBlobStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");

  const artifactUrlsRef = useRef<ArtifactUrls>({
    registerImageUrl: null,
    loginImageUrl: null,
    evidenceImageUrl: null,
    videoUrl: null
  });
  const cardEvidenceImageUrlsRef = useRef<(string | null)[]>([]);
  const viewerVideoRef = useRef<HTMLVideoElement | null>(null);
  const artifactsControllerRef = useRef<AbortController | null>(null);
  const taskIdRef = useRef<number | null>(null);
  const videoBlobPromiseRef = useRef<Promise<string | null> | null>(null);

  const renderStatus = (value?: string) => {
    if (!value) return <span className="text-slate-400">-</span>;
    const label = STATUS_LABELS[value as TaskStatus] ?? value;

    const icon: Record<string, JSX.Element | null> = {
      PENDING: null,
      RUNNING: <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />,
      SUCCESS: null,
      FAILED: null
    };

    const pillClass = STATUS_STYLES[value as TaskStatus] || "bg-slate-100 text-slate-600 border border-slate-200";

    return (
      <span className={cn("inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium", pillClass)}>
        {icon[value]}
        {label}
      </span>
    );
  };

  const formatDurationSeconds = (value?: number | null) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "-";
    const totalSeconds = Math.max(0, Math.floor(value));
    if (totalSeconds < 60) return `${totalSeconds}秒`;

    const days = Math.floor(totalSeconds / 86_400);
    const hours = Math.floor((totalSeconds % 86_400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (totalSeconds < 3600) return `${minutes}分${seconds}秒`;
    if (totalSeconds < 86_400) return `${hours}小时${minutes}分${seconds}秒`;
    return `${days}天${hours}小时${minutes}分${seconds}秒`;
  };

  const formatTaskDuration = (durationSeconds: number, status?: string) => {
    if (status === "PENDING" || status === "RUNNING") {
      return "-";
    }
    return formatDurationSeconds(durationSeconds);
  };

  const getWaitSeconds = (item: EvidenceItem) => {
    const createdAt = parseDateTime(item.created_at);
    const executedAt = parseDateTime(item.executed_at);
    if (!createdAt || !executedAt) return null;
    return (executedAt.getTime() - createdAt.getTime()) / 1000;
  };

  const handleCopyReplayCommand = useCallback(async () => {
    const url = (task.url ?? "").trim();
    if (!url) {
      toast.error("缺少网址，无法生成命令");
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
        `/evidence/${taskId}/artifact?path=${encodeURIComponent(path)}`,
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
            if (!signal?.aborted && taskIdRef.current === taskId) setVideoBlobStatus("error");
            return null;
          }

          if (signal?.aborted || taskIdRef.current !== taskId) {
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
          if (!signal?.aborted && taskIdRef.current === taskId) setVideoBlobStatus("error");
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

  useEffect(() => {
    taskIdRef.current = task?.id ?? null;
  }, [task]);

  useEffect(() => {
    revokeArtifactUrls(artifactUrlsRef.current);
    artifactUrlsRef.current = {
      registerImageUrl: null,
      loginImageUrl: null,
      evidenceImageUrl: null,
      videoUrl: null
    };
    setArtifactUrls(artifactUrlsRef.current);
    setArtifacts(null);
    setVideoBlobStatus("idle");
    videoBlobPromiseRef.current = null;
    setCardAuthIndex(0);

    if (task.status === "PENDING" || task.status === "RUNNING") {
      setArtifacts({
        register_image_path: null,
        login_image_path: null,
        evidence_image_path: null,
        video_path: null,
        video_seek_seconds: null
      });
      return;
    }

    const controller = new AbortController();
    artifactsControllerRef.current?.abort();
    artifactsControllerRef.current = controller;
    let cancelled = false;
    let prefetchIdleId: number | null = null;
    let prefetchTimeoutId: number | null = null;

    const load = async () => {
      setArtifactsLoading(true);
      try {
        const res = await apiFetch(`/evidence/${task.id}/artifacts`, {
          signal: controller.signal
        });
        if (!res.ok) throw new Error("加载任务产物失败");
        const payload = (await res.json()) as TaskArtifacts;
        if (cancelled) return;
        setArtifacts(payload);

        const [registerImageUrl, loginImageUrl, evidenceImageUrl] = await Promise.all([
          fetchArtifactBlobUrl(task.id, payload.register_image_path, controller.signal),
          fetchArtifactBlobUrl(task.id, payload.login_image_path, controller.signal),
          fetchArtifactBlobUrl(task.id, payload.evidence_image_path, controller.signal)
        ]);

        if (cancelled) {
          revokeArtifactUrls({ registerImageUrl, loginImageUrl, evidenceImageUrl, videoUrl: null });
          return;
        }

        setMediaReady({ login: false, evidence: false });
        setMediaError({ login: false, evidence: false });
        setCardAuthIndex(0);
        artifactUrlsRef.current = { registerImageUrl, loginImageUrl, evidenceImageUrl, videoUrl: null };
        setArtifactUrls(artifactUrlsRef.current);

        // 加载所有取证图片（用于卡片轮播）
        if (payload.evidence_entries_detail && payload.evidence_entries_detail.length > 0) {
          setCardEvidenceLoading(true);
          setCardEvidenceIndex(0);
          // 找到当前封面图在 entries 中的索引
          const currentIndex = payload.evidence_entries_detail.findIndex(
            (entry) => entry.screenshot === payload.evidence_image_path
          );
          const initialIndex = currentIndex >= 0 ? currentIndex : 0;
          setCardEvidenceIndex(initialIndex);

          Promise.all(
            payload.evidence_entries_detail.map((entry) =>
              fetchArtifactBlobUrl(task.id, entry.screenshot, controller.signal)
            )
          )
            .then((urls) => {
              if (!cancelled) {
                // 先清理旧的 URL
                cardEvidenceImageUrlsRef.current.forEach((url) => {
                  if (url) URL.revokeObjectURL(url);
                });
                cardEvidenceImageUrlsRef.current = urls;
                setCardEvidenceImageUrls(urls);
                // 更新 evidenceImageUrl 为当前索引的图片
                if (urls[initialIndex]) {
                  artifactUrlsRef.current.evidenceImageUrl = urls[initialIndex];
                  setArtifactUrls({ ...artifactUrlsRef.current });
                }
              } else {
                // 取消时释放已加载的 URL
                urls.forEach((url) => {
                  if (url) URL.revokeObjectURL(url);
                });
              }
            })
            .catch(() => {
              // 忽略错误
            })
            .finally(() => {
              if (!cancelled) {
                setCardEvidenceLoading(false);
              }
            });
        } else {
          // 没有 entries_detail，重置状态
          setCardEvidenceImageUrls([]);
          setCardEvidenceIndex(0);
        }

        if (payload.video_path) {
          const schedulePrefetch = () => {
            if (cancelled) return;
            void ensureVideoBlobUrl(task.id, payload.video_path, controller.signal);
          };

          if (typeof window !== "undefined") {
            const win = window as unknown as {
              requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
              cancelIdleCallback?: (id: number) => void;
            };

            if (win.requestIdleCallback) {
              prefetchIdleId = win.requestIdleCallback(schedulePrefetch, { timeout: 1500 });
            } else {
              prefetchTimeoutId = window.setTimeout(schedulePrefetch, 500);
            }
          }
        }
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
      if (typeof window !== "undefined") {
        const win = window as unknown as { cancelIdleCallback?: (id: number) => void };
        if (prefetchIdleId !== null && win.cancelIdleCallback) win.cancelIdleCallback(prefetchIdleId);
        if (prefetchTimeoutId !== null) window.clearTimeout(prefetchTimeoutId);
      }
      revokeArtifactUrls(artifactUrlsRef.current);
      artifactUrlsRef.current = {
        registerImageUrl: null,
        loginImageUrl: null,
        evidenceImageUrl: null,
        videoUrl: null
      };
      artifactsControllerRef.current = null;
      // 清理卡片轮播图片 URL
      cardEvidenceImageUrlsRef.current.forEach((url) => {
        if (url) URL.revokeObjectURL(url);
      });
      cardEvidenceImageUrlsRef.current = [];
      setCardEvidenceImageUrls([]);
      setCardEvidenceIndex(0);
    };
  }, [ensureVideoBlobUrl, fetchArtifactBlobUrl, revokeArtifactUrls, task]);

  useEffect(() => {
    setMediaReady({ login: false, evidence: false });
    setMediaError({ login: false, evidence: false });
    setCurrentAuthIndex(0);
  }, [task]);

  useEffect(() => {
    if (!viewer) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setViewer(null);
        return;
      }
      // 轮播切换：只在查看器显示图片且有多个图片时生效
      if (viewer.type === "image" && viewer.evidenceEntries && viewer.evidenceEntries.length > 1) {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          const newIndex =
            currentEvidenceIndex > 0 ? currentEvidenceIndex - 1 : viewer.evidenceEntries.length - 1;
          setCurrentEvidenceIndex(newIndex);
          if (viewer.currentEvidenceIndex !== undefined) {
            setViewer({ ...viewer, currentEvidenceIndex: newIndex });
          }
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          const newIndex =
            currentEvidenceIndex < viewer.evidenceEntries.length - 1 ? currentEvidenceIndex + 1 : 0;
          setCurrentEvidenceIndex(newIndex);
          if (viewer.currentEvidenceIndex !== undefined) {
            setViewer({ ...viewer, currentEvidenceIndex: newIndex });
          }
        }
      }
      // 认证截图轮播
      else if (viewer.type === "image" && viewer.authEntries && viewer.authEntries.length > 1) {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          const newIndex =
            currentAuthIndex > 0 ? currentAuthIndex - 1 : viewer.authEntries.length - 1;
          setCurrentAuthIndex(newIndex);
          const newImage = viewer.authEntries[newIndex];
          setViewer({ ...viewer, currentAuthIndex: newIndex, src: newImage.url, title: newImage.label });
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          const newIndex =
            currentAuthIndex < viewer.authEntries.length - 1 ? currentAuthIndex + 1 : 0;
          setCurrentAuthIndex(newIndex);
          const newImage = viewer.authEntries[newIndex];
          setViewer({ ...viewer, currentAuthIndex: newIndex, src: newImage.url, title: newImage.label });
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [viewer, currentEvidenceIndex, currentAuthIndex]);

  // 加载当前索引的取证图片
  useEffect(() => {
    if (
      !viewer ||
      viewer.type !== "image" ||
      !viewer.evidenceEntries ||
      viewer.evidenceEntries.length === 0 ||
      !task ||
      currentEvidenceIndex < 0 ||
      currentEvidenceIndex >= viewer.evidenceEntries.length
    )
      return;

    const entry = viewer.evidenceEntries[currentEvidenceIndex];
    if (!entry) return;

    setEvidenceImageLoading(true);
    const controller = new AbortController();

    fetchArtifactBlobUrl(task.id, entry.screenshot, controller.signal)
      .then((url) => {
        if (!controller.signal.aborted && url) {
          // 释放旧的 URL
          if (currentEvidenceImageUrl) {
            URL.revokeObjectURL(currentEvidenceImageUrl);
          }
          setCurrentEvidenceImageUrl(url);
          setViewer((prev) => {
            if (!prev || prev.type !== "image") return prev;
            return {
              ...prev,
              title: "取证截图",
              src: url,
              currentEvidenceIndex: currentEvidenceIndex,
            };
          });
        }
      })
      .catch(() => {
        // 忽略错误
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setEvidenceImageLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [currentEvidenceIndex, viewer?.type, viewer?.evidenceEntries?.length, task?.id, fetchArtifactBlobUrl]);

  // 清理图片 URL
  useEffect(() => {
    return () => {
      if (currentEvidenceImageUrl) {
        URL.revokeObjectURL(currentEvidenceImageUrl);
      }
    };
  }, [currentEvidenceImageUrl]);

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

  const getViewerBaselineSeconds = () => {
    const raw = viewer?.seekSeconds;
    if (typeof raw !== "number" || Number.isNaN(raw) || raw <= 0) return 0;
    return raw;
  };

  const handleViewerVideoLoadedMetadata = () => {
    if (!viewerVideoRef.current) return;

    const duration = viewerVideoRef.current.duration;
    const hasDuration = typeof duration === "number" && Number.isFinite(duration) && duration > 0;
    const baseline = getViewerBaselineSeconds();
    const safeBaseline = hasDuration ? Math.min(baseline, Math.max(0, duration - 0.1)) : baseline;
    const safeSeek = safeBaseline;
    if (safeSeek > 0) viewerVideoRef.current.currentTime = safeSeek;
    viewerVideoRef.current.defaultPlaybackRate = 3;
    viewerVideoRef.current.playbackRate = 3;

    setViewerPlayback((prev) => ({
      ...prev,
      duration: hasDuration ? duration : 0,
      currentTime: viewerVideoRef.current?.currentTime ?? 0,
      dragValue: 0
    }));
  };

  const handleViewerPlayOverlayClick = async () => {
    if (!viewerVideoRef.current) return;
    const baseline = getViewerBaselineSeconds();
    if (baseline > 0 && viewerVideoRef.current.currentTime < baseline) {
      viewerVideoRef.current.currentTime = baseline;
    }
    if (viewerVideoState.ended) {
      const seekSeconds = viewer?.seekSeconds;
      const duration = viewerVideoRef.current.duration;
      const hasDuration = typeof duration === "number" && Number.isFinite(duration) && duration > 0;
      const canSeek =
        typeof seekSeconds === "number" && !Number.isNaN(seekSeconds) && seekSeconds > 0;
      const target = canSeek
        ? hasDuration
          ? Math.min(seekSeconds, Math.max(0, duration - 0.1))
          : seekSeconds
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

  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

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

  const formatClock = (seconds: number) => {
    const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
    const whole = Math.floor(safe);
    const minutes = Math.floor(whole / 60);
    const remainder = whole % 60;
    return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  };

  if (!task) return null;

  return (
    <>
      {/* 任务详情弹窗 */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        onClick={onClose}
      >
        <div
          className="relative w-full max-w-6xl rounded-2xl bg-white shadow-2xl"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label="注册取证任务详情"
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <div className="space-y-1">
              <h3 className="text-lg font-semibold text-slate-900">注册取证任务详情</h3>
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
              <div className="break-all font-medium text-slate-800">{task.account || "-"}</div>
            </div>
            <div className="space-y-1">
              <div className="text-slate-500">密码</div>
              <div className="break-all font-medium text-slate-800">{task.password || "-"}</div>
            </div>
            <div className="space-y-1">
              <div className="text-slate-500">任务状态</div>
              <div className="flex items-center gap-2">{renderStatus(task.status)}</div>
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
                        🤖 {formatTokenCount(task.llm_usage.total_tokens)}
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
              {task.status === "FAILED" && task.failure_type && (
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
                  <div className="text-sm font-semibold text-slate-800">认证截图</div>
                </div>
                {artifactsLoading ? (
                  <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                    <div className="absolute inset-0 animate-pulse bg-slate-100/70" />
                    <MediaLoadingOverlay label="加载中..." />
                  </div>
                ) : (() => {
                  // 准备认证图片数组
                  const authImages: Array<{ type: 'register' | 'login'; url: string; label: string }> = [];
                  if (artifactUrls.registerImageUrl) {
                    authImages.push({ type: 'register', url: artifactUrls.registerImageUrl, label: '注册截图' });
                  }
                  if (artifactUrls.loginImageUrl) {
                    authImages.push({ type: 'login', url: artifactUrls.loginImageUrl, label: '登录截图' });
                  }
                  const hasMultipleImages = authImages.length > 1;
                  const currentImage = authImages[cardAuthIndex];

                  return currentImage ? (
                    <div className="relative">
                      <button
                        type="button"
                        className="group relative block w-full"
                        onClick={() => {
                          setViewer({
                            type: "image",
                            title: currentImage.label,
                            src: currentImage.url,
                            authEntries: authImages.length > 1 ? authImages : null,
                            currentAuthIndex: cardAuthIndex
                          });
                          setCurrentAuthIndex(cardAuthIndex);
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
                          src={currentImage.url}
                          alt={currentImage.label}
                          className={cn(
                            "w-full aspect-[16/10] rounded-xl border border-slate-200 object-contain bg-slate-50 cursor-zoom-in group-hover:shadow-sm transition-opacity",
                            mediaReady.login && !mediaError.login ? "opacity-100" : "opacity-0"
                          )}
                          onLoad={() => setMediaReady((prev) => ({ ...prev, login: true }))}
                          onError={() => setMediaError((prev) => ({ ...prev, login: true }))}
                        />
                      </button>
                      {hasMultipleImages ? (
                        <>
                          {/* 左箭头 */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setCardAuthIndex((prev) => prev > 0 ? prev - 1 : authImages.length - 1);
                              setMediaReady((prev) => ({ ...prev, login: false }));
                              setMediaError((prev) => ({ ...prev, login: false }));
                            }}
                            className="absolute left-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/40 p-1.5 text-white backdrop-blur-sm transition hover:bg-black/60"
                            aria-label="上一张"
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </button>
                          {/* 右箭头 */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setCardAuthIndex((prev) => prev < authImages.length - 1 ? prev + 1 : 0);
                              setMediaReady((prev) => ({ ...prev, login: false }));
                              setMediaError((prev) => ({ ...prev, login: false }));
                            }}
                            className="absolute right-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/40 p-1.5 text-white backdrop-blur-sm transition hover:bg-black/60"
                            aria-label="下一张"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </button>
                          {/* 底部指示器 */}
                          <div className="absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/40 px-3 py-1 text-xs text-white backdrop-blur-sm">
                            {cardAuthIndex + 1} / {authImages.length} - {currentImage.label}
                          </div>
                        </>
                      ) : null}
                    </div>
                  ) : (
                    <div className="flex w-full aspect-[16/10] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                      不存在
                    </div>
                  );
                })()}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm font-semibold text-slate-800">取证截图</div>
                </div>
                {artifactsLoading || cardEvidenceLoading ? (
                  <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                    <div className="absolute inset-0 animate-pulse bg-slate-100/70" />
                    <MediaLoadingOverlay label="加载中..." />
                  </div>
                ) : (() => {
                  // 确定要显示的图片 URL（使用 ref 获取最新值）
                  const urls = cardEvidenceImageUrlsRef.current;
                  const displayImageUrl =
                    urls.length > 0 && urls[cardEvidenceIndex]
                      ? urls[cardEvidenceIndex]
                      : artifactUrls.evidenceImageUrl;
                  const hasMultipleImages = urls.length > 1;
                  const currentEntry = artifacts?.evidence_entries_detail?.[cardEvidenceIndex];

                  return displayImageUrl ? (
                    <div className="relative">
                      <button
                        type="button"
                        className="group relative block w-full"
                        onClick={async () => {
                          const entries = artifacts?.evidence_entries_detail;
                          if (entries && entries.length > 0) {
                            const initialIndex = cardEvidenceIndex;
                            setCurrentEvidenceIndex(initialIndex);
                            const entry = entries[initialIndex];
                            if (entry) {
                              // 使用 ref 获取最新值
                              const urls = cardEvidenceImageUrlsRef.current;
                              const imageUrl = urls[initialIndex] || await fetchArtifactBlobUrl(
                                task.id,
                                entry.screenshot,
                                artifactsControllerRef.current?.signal
                              );
                              if (imageUrl) {
                                setCurrentEvidenceImageUrl(imageUrl);
                                setViewer({
                                  type: "image",
                                  title: "取证截图",
                                  src: imageUrl,
                                  evidenceEntries: entries,
                                  currentEvidenceIndex: initialIndex,
                                });
                              }
                            }
                          } else {
                            setViewer({
                              type: "image",
                              title: "取证截图",
                              src: displayImageUrl,
                            });
                          }
                        }}
                      >
                        {!mediaReady.evidence && !mediaError.evidence ? (
                          <MediaLoadingOverlay label="加载中..." />
                        ) : null}
                        {mediaError.evidence ? (
                          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                            加载失败
                          </div>
                        ) : null}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={displayImageUrl}
                          alt="取证截图"
                          className={cn(
                            "w-full aspect-[16/10] rounded-xl border border-slate-200 object-contain bg-slate-50 cursor-zoom-in group-hover:shadow-sm transition-opacity",
                            mediaReady.evidence && !mediaError.evidence ? "opacity-100" : "opacity-0"
                          )}
                          onLoad={() => setMediaReady((prev) => ({ ...prev, evidence: true }))}
                          onError={() => setMediaError((prev) => ({ ...prev, evidence: true }))}
                        />
                      </button>
                      {hasMultipleImages ? (
                        <>
                          {/* 左箭头 */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              const urls = cardEvidenceImageUrlsRef.current;
                              if (urls.length === 0) return;
                              const newIndex =
                                cardEvidenceIndex > 0
                                  ? cardEvidenceIndex - 1
                                  : urls.length - 1;
                              setCardEvidenceIndex(newIndex);
                              // 更新显示的图片 URL（使用 ref 获取最新值）
                              const newUrl = urls[newIndex];
                              if (newUrl) {
                                artifactUrlsRef.current.evidenceImageUrl = newUrl;
                                setArtifactUrls({ ...artifactUrlsRef.current });
                                setMediaReady((prev) => ({ ...prev, evidence: false }));
                                setMediaError((prev) => ({ ...prev, evidence: false }));
                              }
                            }}
                            className="absolute left-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/40 p-1.5 text-white backdrop-blur-sm transition hover:bg-black/60"
                            aria-label="上一张"
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </button>
                          {/* 右箭头 */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              const urls = cardEvidenceImageUrlsRef.current;
                              if (urls.length === 0) return;
                              const newIndex =
                                cardEvidenceIndex < urls.length - 1
                                  ? cardEvidenceIndex + 1
                                  : 0;
                              setCardEvidenceIndex(newIndex);
                              // 更新显示的图片 URL（使用 ref 获取最新值）
                              const newUrl = urls[newIndex];
                              if (newUrl) {
                                artifactUrlsRef.current.evidenceImageUrl = newUrl;
                                setArtifactUrls({ ...artifactUrlsRef.current });
                                setMediaReady((prev) => ({ ...prev, evidence: false }));
                                setMediaError((prev) => ({ ...prev, evidence: false }));
                              }
                            }}
                            className="absolute right-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/40 p-1.5 text-white backdrop-blur-sm transition hover:bg-black/60"
                            aria-label="下一张"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </button>
                          {/* 底部指示器 */}
                          <div className="absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/40 px-3 py-1 text-xs text-white backdrop-blur-sm">
                            {cardEvidenceIndex + 1} / {cardEvidenceImageUrlsRef.current.length}
                            {currentEntry && ` - ${extractEntryLabel(currentEntry.screenshot)}`}
                          </div>
                        </>
                      ) : null}
                    </div>
                  ) : (
                    <div className="flex w-full aspect-[16/10] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                      不存在
                    </div>
                  );
                })()}
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
                    <MediaLoadingOverlay label="加载中..." />
                  </div>
                ) : artifacts?.video_path ? (
                  <button
                    type="button"
                    className="group relative block w-full"
                    onClick={async () => {
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
                    {(() => {
                      const coverImageUrl = artifactUrls.registerImageUrl || artifactUrls.loginImageUrl;
                      return coverImageUrl && !mediaError.login ? (
                        <>
                          {!mediaReady.login ? <MediaLoadingOverlay label="加载中..." /> : null}
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={coverImageUrl}
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
                      );
                    })()}
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
      </div>

      {/* 图片/视频预览器 */}
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
                <div className="relative">
                  {(viewer.evidenceEntries && viewer.evidenceEntries.length > 1) ||
                   (viewer.authEntries && viewer.authEntries.length > 1) ? (
                    <>
                      {/* 左箭头 */}
                      <button
                        type="button"
                        onClick={() => {
                          if (viewer.evidenceEntries && viewer.evidenceEntries.length > 1) {
                            const newIndex =
                              currentEvidenceIndex > 0
                                ? currentEvidenceIndex - 1
                                : viewer.evidenceEntries.length - 1;
                            setCurrentEvidenceIndex(newIndex);
                            setViewer({ ...viewer, currentEvidenceIndex: newIndex });
                          } else if (viewer.authEntries && viewer.authEntries.length > 1) {
                            const newIndex =
                              currentAuthIndex > 0
                                ? currentAuthIndex - 1
                                : viewer.authEntries.length - 1;
                            setCurrentAuthIndex(newIndex);
                            const newImage = viewer.authEntries[newIndex];
                            setViewer({ ...viewer, currentAuthIndex: newIndex, src: newImage.url, title: newImage.label });
                          }
                        }}
                        className="absolute left-4 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white backdrop-blur-sm transition hover:bg-black/60"
                        aria-label="上一张"
                      >
                        <ChevronLeft className="h-6 w-6" />
                      </button>
                      {/* 右箭头 */}
                      <button
                        type="button"
                        onClick={() => {
                          if (viewer.evidenceEntries && viewer.evidenceEntries.length > 1) {
                            const newIndex =
                              currentEvidenceIndex < viewer.evidenceEntries.length - 1
                                ? currentEvidenceIndex + 1
                                : 0;
                            setCurrentEvidenceIndex(newIndex);
                            setViewer({ ...viewer, currentEvidenceIndex: newIndex });
                          } else if (viewer.authEntries && viewer.authEntries.length > 1) {
                            const newIndex =
                              currentAuthIndex < viewer.authEntries.length - 1
                                ? currentAuthIndex + 1
                                : 0;
                            setCurrentAuthIndex(newIndex);
                            const newImage = viewer.authEntries[newIndex];
                            setViewer({ ...viewer, currentAuthIndex: newIndex, src: newImage.url, title: newImage.label });
                          }
                        }}
                        className="absolute right-4 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white backdrop-blur-sm transition hover:bg-black/60"
                        aria-label="下一张"
                      >
                        <ChevronRight className="h-6 w-6" />
                      </button>
                      {/* 底部指示器 */}
                      <div className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/40 px-4 py-2 text-sm text-white backdrop-blur-sm">
                        {viewer.evidenceEntries ? (
                          <>
                            {currentEvidenceIndex + 1} / {viewer.evidenceEntries.length} -{" "}
                            {viewer.evidenceEntries[currentEvidenceIndex]
                              ? extractEntryLabel(viewer.evidenceEntries[currentEvidenceIndex].screenshot)
                              : extractEntryLabel(viewer.title)}
                          </>
                        ) : viewer.authEntries ? (
                          <>
                            {currentAuthIndex + 1} / {viewer.authEntries.length} - {viewer.authEntries[currentAuthIndex]?.label}
                          </>
                        ) : null}
                      </div>
                    </>
                  ) : null}
                  {evidenceImageLoading ? (
                    <div className="flex min-h-[400px] items-center justify-center">
                      <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                    </div>
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={viewer.src ?? currentEvidenceImageUrl ?? ""}
                      alt={viewer.title}
                      className="max-h-[80vh] w-full rounded-xl bg-white object-contain"
                    />
                  )}
                </div>
              ) : (
                <div className="relative">
                  <div className="relative w-full aspect-[16/10] max-h-[80vh] overflow-hidden rounded-xl bg-black">
                    {viewerVideoFetch.loading || (!viewerVideoFetch.ready && !viewerVideoFetch.error) ? (
                      <div className="absolute inset-0 z-20">
                        <MediaLoadingOverlay label={videoBlobStatus === "loading" ? "加载视频中..." : "加载中..."} />
                      </div>
                    ) : null}
                    {viewerVideoFetch.error ? (
                      <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
                        加载失败
                      </div>
                    ) : null}
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
    </>
  );
}

