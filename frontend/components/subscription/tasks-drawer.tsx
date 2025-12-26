"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2, Pause, Play, RotateCcw, Search } from "lucide-react";
import { toast } from "sonner";

// DashboardShell removed - this component is used inside a Sheet
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { apiFetch } from "@/lib/api";
import { formatDateTime, parseDateTime } from "@/lib/datetime";
import { cn } from "@/lib/utils";
import type {
  SubscriptionItem,
  TaskArtifacts,
  ArtifactUrls,
  MediaFlags,
  SubscriptionListResponse,
} from "@/types/subscription";
import {
  STATUS_LABELS,
  STATUS_STYLES,
  type TaskStatus,
  type FailureTypeItem,
  type FailureTypesResponse,
} from "@/types/common";

const PAGE_SIZE = 15;

function shellQuoteSingle(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
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

function SubscriptionContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [data, setData] = useState<SubscriptionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [failureTypeFilter, setFailureTypeFilter] = useState("ALL");
  const [timeRangeFilter, setTimeRangeFilter] = useState("ALL");
  const [loading, setLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<SubscriptionItem | null>(null);
  const [artifacts, setArtifacts] = useState<TaskArtifacts | null>(null);
  const [artifactUrls, setArtifactUrls] = useState<ArtifactUrls>({
    loginImageUrl: null,
    extractImageUrl: null,
    videoUrl: null
  });
  const [viewer, setViewer] = useState<{
    type: "image" | "video";
    title: string;
    src: string | null;
    seekSeconds?: number | null;
  } | null>(null);
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
    extract: false
  });
  const [mediaError, setMediaError] = useState<MediaFlags>({
    login: false,
    extract: false
  });
  const [failureTypeStats, setFailureTypeStats] = useState<
    Array<{ type: string; label: string; count: number }>
  >([]);
  const [failureTypes, setFailureTypes] = useState<FailureTypeItem[]>([]);

  // 获取失败类型列表
  useEffect(() => {
    const fetchFailureTypes = async () => {
      try {
        const res = await apiFetch("/subscription/failure-types");
        if (!res.ok) {
          throw new Error("获取失败类型列表失败");
        }
        const data = (await res.json()) as FailureTypesResponse;
        setFailureTypes(data.items);
      } catch (error) {
        console.error("获取失败类型列表失败:", error);
        toast.error("获取失败类型列表失败");
      }
    };
    fetchFailureTypes();
  }, []);

  const handleCopyReplayCommand = useCallback(async () => {
    if (!selectedItem) return;

    const url = (selectedItem.url ?? "").trim();
    const account = (selectedItem.account ?? "").trim();
    const password = (selectedItem.password ?? "").trim();
    if (!url || !account || !password) {
      toast.error("缺少网址/用户名/密码，无法生成命令");
      return;
    }

    try {
      await navigator.clipboard.writeText(buildReplayCommand(selectedItem));
      toast.success("复制成功");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  }, [selectedItem]);
  const artifactUrlsRef = useRef<ArtifactUrls>({
    loginImageUrl: null,
    extractImageUrl: null,
    videoUrl: null
  });
  const viewerVideoRef = useRef<HTMLVideoElement | null>(null);
  const artifactsControllerRef = useRef<AbortController | null>(null);
  const selectedItemIdRef = useRef<number | null>(null);
  const videoBlobPromiseRef = useRef<Promise<string | null> | null>(null);
  const [videoBlobStatus, setVideoBlobStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [viewerVideoFetch, setViewerVideoFetch] = useState({ loading: false, error: false, ready: false });

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total]
  );

  const getPageItems = (current: number, totalCount: number): Array<number | string> => {
    if (totalCount <= 7) {
      return Array.from({ length: totalCount }, (_, idx) => idx + 1);
    }

    const items: Array<number | string> = [1];
    const start = Math.max(2, current - 1);
    const end = Math.min(totalCount - 1, current + 1);

    if (start > 2) items.push("...");
    for (let p = start; p <= end; p += 1) {
      items.push(p);
    }
    if (end < totalCount - 1) items.push("...");
    items.push(totalCount);

    return items;
  };

  const pageItems = useMemo(() => getPageItems(page, totalPages), [page, totalPages]);

  const fetchData = useCallback(
    async (params: { page: number; q: string; status: string; failureType: string; timeRange: string }) => {
      setLoading(true);
      try {
        const searchParams = new URLSearchParams({
          page: String(params.page),
          page_size: String(PAGE_SIZE)
        });
        if (params.q) searchParams.set("q", params.q);
        if (params.status && params.status !== "ALL") searchParams.set("status", params.status);
        if (params.failureType && params.failureType !== "ALL") searchParams.set("failure_type", params.failureType);
        if (params.timeRange && params.timeRange !== "ALL") searchParams.set("executed_within", params.timeRange);

        const res = await apiFetch(
          `/subscription/list?${searchParams.toString()}`
        );
        if (!res.ok) throw new Error("加载失败");
        const payload = (await res.json()) as SubscriptionListResponse;
        setData(payload.items);
        setTotal(payload.total);
        setPage(payload.page);
        setPageInput(String(payload.page));
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const fetchFailureTypeStats = useCallback(async (timeRange?: string) => {
    try {
      // 构建查询参数，传递时间范围
      const params = new URLSearchParams();
      if (timeRange && timeRange !== "ALL") {
        params.set('executed_within', timeRange);
      }
      const url = `/subscription/stats${params.toString() ? `?${params.toString()}` : ''}`;
      
      const res = await apiFetch(url);
      if (!res.ok) return;
      const payload = await res.json();
      setFailureTypeStats(payload.failure_type_distribution || []);
    } catch (error) {
      console.error('Failed to fetch failure type stats:', error);
    }
  }, []);

  useEffect(() => {
    // 从 URL 读取所有参数
    const urlPage = searchParams.get("page");
    const urlQuery = searchParams.get("q") || ""; // 默认空字符串
    let urlStatus = searchParams.get("status") || "ALL";
    let urlFailureType = searchParams.get("failure_type") || "ALL";
    const urlTimeRange = searchParams.get("executed_within") || "ALL";

    // 修正：只有 status=FAILED 时才保留 failure_type（与现有逻辑一致）
    // 支持大小写不敏感比较，以兼容不同来源的 URL
    if (urlStatus.toUpperCase() !== "FAILED") {
      urlFailureType = "ALL";
    }

    // 解析并验证 page（防止 NaN）
    let pageNum = 1;
    if (urlPage) {
      const parsed = parseInt(urlPage, 10);
      if (!isNaN(parsed) && parsed >= 1) {
        pageNum = parsed;
      }
    }

    // 无条件更新所有状态（确保与 URL 完全同步）
    setPage(pageNum);
    setPageInput(String(pageNum));
    setQuery(urlQuery); // 即使是空字符串也设置
    setStatusFilter(urlStatus);
    setFailureTypeFilter(urlFailureType);
    setTimeRangeFilter(urlTimeRange);

    // 使用 URL 参数获取数据
    fetchData({
      page: pageNum,
      status: urlStatus,
      failureType: urlFailureType,
      q: urlQuery,
      timeRange: urlTimeRange
    });
    
    // 获取失败类型统计，传递时间范围参数
    fetchFailureTypeStats(urlTimeRange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchData({
        page,
        q: query,
        status: statusFilter,
        failureType: failureTypeFilter,
        timeRange: timeRangeFilter
      });
      // 定时刷新时也传递当前时间范围
      fetchFailureTypeStats(timeRangeFilter);
    }, 30_000);

    return () => clearInterval(interval);
  }, [fetchData, fetchFailureTypeStats, page, query, statusFilter, failureTypeFilter, timeRangeFilter]);

  const handleSearch = () => {
    const trimmedQuery = query.trim();
    setQuery(trimmedQuery);

    // 直接更新状态并获取数据
    setPage(1);
    setPageInput("1");
    fetchData({ 
      page: 1, 
      q: trimmedQuery, 
      status: statusFilter, 
      failureType: failureTypeFilter, 
      timeRange: timeRangeFilter 
    });
  };

  const statusOptions: Array<{ value: string; label: string }> = [
    { value: "ALL", label: "全部" },
    { value: "SUCCESS", label: "成功" },
    { value: "FAILED", label: "失败" },
    { value: "RUNNING", label: "执行中" },
    { value: "PENDING", label: "待执行" }
  ];

  // 从 API 获取的失败类型构建标签映射
  const failureTypeLabel: Record<string, string> = useMemo(() => {
    return failureTypes.reduce((acc, item) => {
      acc[item.value] = item.label;
      return acc;
    }, {} as Record<string, string>);
  }, [failureTypes]);

  const failureTypeOptions: Array<{ value: string; label: string }> = useMemo(() => {
    const baseOptions = [
      { value: "ALL", label: "全部" }
    ];

    // 创建统计数据的映射表（来自后端API，匹配当前时间范围）
    const statsMap = new Map(
      failureTypeStats.map(stat => [stat.type, stat.count])
    );

    // 使用从 API 获取的失败类型列表（已按业务优先级排序）
    const optionsWithCount = failureTypes.map(option => {
      const count = statsMap.get(option.value);
      return {
        value: option.value,
        label: count !== undefined ? `${option.label}(${count})` : option.label
      };
    });

    return [...baseOptions, ...optionsWithCount];
  }, [failureTypeStats, failureTypes]);

  const timeRangeOptions: Array<{ value: string; label: string }> = [
    { value: "ALL", label: "全部" },
    { value: "today", label: "今天" },
    { value: "yesterday", label: "昨天" },
    { value: "3d", label: "最近3天" },
    { value: "7d", label: "最近7天" },
    { value: "30d", label: "最近30天" }
  ];

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

  const getWaitSeconds = (item: SubscriptionItem) => {
    const createdAt = parseDateTime(item.created_at);
    const executedAt = parseDateTime(item.executed_at);
    if (!createdAt || !executedAt) return null;
    return (executedAt.getTime() - createdAt.getTime()) / 1000;
  };

  const handlePageChange = (nextPage: number) => {
    // 直接更新状态并获取数据
    setPage(nextPage);
    setPageInput(String(nextPage));
    fetchData({ 
      page: nextPage, 
      q: query, 
      status: statusFilter, 
      failureType: failureTypeFilter, 
      timeRange: timeRangeFilter 
    });
  };

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
            if (!signal?.aborted && selectedItemIdRef.current === taskId) setVideoBlobStatus("error");
            return null;
          }

          if (signal?.aborted || selectedItemIdRef.current !== taskId) {
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
          if (!signal?.aborted && selectedItemIdRef.current === taskId) setVideoBlobStatus("error");
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
    selectedItemIdRef.current = selectedItem?.id ?? null;
  }, [selectedItem]);

  useEffect(() => {
    if (!selectedItem) {
      revokeArtifactUrls(artifactUrlsRef.current);
      artifactUrlsRef.current = {
        loginImageUrl: null,
        extractImageUrl: null,
        videoUrl: null
      };
      setArtifactUrls(artifactUrlsRef.current);
      setArtifacts(null);
      setArtifactsLoading(false);
      setVideoBlobStatus("idle");
      videoBlobPromiseRef.current = null;
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
    setVideoBlobStatus("idle");
    videoBlobPromiseRef.current = null;

    if (selectedItem.status === "PENDING" || selectedItem.status === "RUNNING") {
      setArtifacts({
        status: selectedItem.status,
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
    let prefetchIdleId: number | null = null;
    let prefetchTimeoutId: number | null = null;

    const load = async () => {
      setArtifactsLoading(true);
      try {
        const res = await apiFetch(`/subscription/${selectedItem.id}/artifacts`, {
          signal: controller.signal
        });
        if (!res.ok) throw new Error("加载任务产物失败");
        const payload = (await res.json()) as TaskArtifacts;
        if (cancelled) return;
        setArtifacts(payload);

        const [loginImageUrl, extractImageUrl] = await Promise.all([
          fetchArtifactBlobUrl(selectedItem.id, payload.login_image_path, controller.signal),
          fetchArtifactBlobUrl(selectedItem.id, payload.extract_image_path, controller.signal)
        ]);

        if (cancelled) {
          revokeArtifactUrls({ loginImageUrl, extractImageUrl, videoUrl: null });
          return;
        }

        setMediaReady({ login: false, extract: false });
        setMediaError({ login: false, extract: false });
        artifactUrlsRef.current = { loginImageUrl, extractImageUrl, videoUrl: null };
        setArtifactUrls(artifactUrlsRef.current);

        if (payload.video_path) {
          const schedulePrefetch = () => {
            if (cancelled) return;
            void ensureVideoBlobUrl(selectedItem.id, payload.video_path, controller.signal);
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
        loginImageUrl: null,
        extractImageUrl: null,
        videoUrl: null
      };
      artifactsControllerRef.current = null;
    };
  }, [ensureVideoBlobUrl, fetchArtifactBlobUrl, revokeArtifactUrls, selectedItem]);

  useEffect(() => {
    if (!selectedItem) return;
    setMediaReady({ login: false, extract: false });
    setMediaError({ login: false, extract: false });
  }, [selectedItem]);

  useEffect(() => {
    if (!viewer) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setViewer(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [viewer]);

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
    const seekSeconds = viewer?.seekSeconds;
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

  const handlePageJump = () => {
    const value = parseInt(pageInput, 10);
    if (Number.isNaN(value)) return;
    const target = Math.min(Math.max(1, value), totalPages);

    // 直接更新状态并获取数据
    setPage(target);
    setPageInput(String(target));
    fetchData({ 
      page: target, 
      q: query, 
      status: statusFilter, 
      failureType: failureTypeFilter, 
      timeRange: timeRangeFilter 
    });
  };

  const handleStatusChange = (value: string) => {
    const newFailureType = value !== "FAILED" ? "ALL" : failureTypeFilter;

    // 如果切换到 PENDING 或 RUNNING，清空时间范围
    const newTimeRange = (value === "PENDING" || value === "RUNNING") ? "ALL" : timeRangeFilter;

    // 更新状态
    setStatusFilter(value);
    if (value !== "FAILED") {
      setFailureTypeFilter("ALL");
    }
    if (value === "PENDING" || value === "RUNNING") {
      setTimeRangeFilter("ALL");
    }
    setPage(1);
    setPageInput("1");

    // 直接获取数据，使用新值
    fetchData({ 
      page: 1, 
      q: query, 
      status: value, 
      failureType: newFailureType, 
      timeRange: newTimeRange 
    });
  };

  const handleFailureTypeChange = (value: string) => {
    setFailureTypeFilter(value);
    setPage(1);
    setPageInput("1");

    // 直接获取数据，使用新值
    fetchData({ 
      page: 1, 
      q: query, 
      status: statusFilter, 
      failureType: value, 
      timeRange: timeRangeFilter 
    });
  };

  const handleTimeRangeChange = (value: string) => {
    setTimeRangeFilter(value);
    setPage(1);
    setPageInput("1");

    // 直接获取数据，使用新值
    fetchData({ 
      page: 1, 
      q: query, 
      status: statusFilter, 
      failureType: failureTypeFilter, 
      timeRange: value 
    });
    // 更新失败类型统计（带时间范围参数）
    fetchFailureTypeStats(value);
  };

  const handleRowClick = (item: SubscriptionItem) => {
    setViewer(null);
    setSelectedItem(item);
  };

  const handleCloseModal = () => {
    setViewer(null);
    setSelectedItem(null);
  };

  return (
    <div className="flex h-full flex-col">
      {/* 顶部操作栏 */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-700">状态</span>
            <Select
              value={statusFilter}
              onValueChange={handleStatusChange}
              disabled={loading}
            >
              <SelectTrigger className="w-[120px] h-10 border-slate-200 bg-white shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
                <SelectValue placeholder="全部" />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((option) => (
                  <SelectItem key={option.value || "all"} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {statusFilter === "FAILED" && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">失败类型</span>
              <Select
                value={failureTypeFilter}
                onValueChange={handleFailureTypeChange}
                disabled={loading}
              >
                <SelectTrigger className="w-[180px] h-10 border-slate-200 bg-white shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  {failureTypeOptions.map((option) => (
                    <SelectItem key={option.value || "all"} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {/* 只在 SUCCESS 或 FAILED 状态时显示时间范围选择框 */}
          {(statusFilter === "ALL" || statusFilter === "SUCCESS" || statusFilter === "FAILED") && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">时间范围</span>
              <Select
                value={timeRangeFilter}
                onValueChange={handleTimeRangeChange}
                disabled={loading}
              >
                <SelectTrigger className="w-[140px] h-10 border-slate-200 bg-white shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  {timeRangeOptions.map((option) => (
                    <SelectItem key={option.value || "all"} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <div className="relative flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-[0_6px_18px_rgba(15,23,42,0.06)]">
          <Search className="pointer-events-none absolute left-4 h-4 w-4 text-slate-400" />
          <Input
            placeholder="按 URL 搜索"
            className="h-10 w-56 border-0 bg-transparent pl-9 pr-24 text-sm shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSearch();
              }
            }}
          />
          <Button
            size="sm"
            className="ml-2 h-9 rounded-lg px-4 bg-sky-500 text-white shadow-sm hover:bg-sky-500/90 disabled:opacity-70"
            onClick={handleSearch}
            disabled={loading}
          >
            搜索
          </Button>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 overflow-y-auto">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="grid grid-cols-[70px_1.4fr_0.65fr_1.1fr_1.1fr_0.8fr_2fr] bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
          <div>ID</div>
          <div>网址</div>
          <div>任务状态</div>
          <div>任务创建时间</div>
          <div>任务执行时间</div>
          <div>任务时长</div>
          <div>任务结果</div>
        </div>
        <div className="divide-y divide-slate-100">
          {loading ? (
            <div className="flex items-center justify-center gap-2 px-4 py-6 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载...
            </div>
          ) : data.length === 0 ? (
            <div className="px-4 py-6 text-sm text-slate-500">暂无数据</div>
          ) : (
            data.map((item, idx) => (
              <div
                key={`${item.id}-${idx}`}
                className={cn(
                  "grid grid-cols-[70px_1.4fr_0.65fr_1.1fr_1.1fr_0.8fr_2fr] items-center px-4 py-3 text-sm text-slate-700",
                  idx % 2 === 0 ? "bg-white" : "bg-slate-50/70",
                  "cursor-pointer transition-colors hover:bg-slate-100/80"
                )}
                onClick={() => handleRowClick(item)}
              >
                <div className="font-mono text-xs text-slate-500">
                  {item.id ?? (page - 1) * PAGE_SIZE + idx + 1}
                </div>
                <div className="truncate pr-4" title={item.url}>
                  {item.url}
                </div>
                <div className="truncate pr-4 text-slate-600">
                  {renderStatus(item.status)}
                </div>
                <div className="truncate pr-4" title={item.created_at || undefined}>
                  {formatDateTime(item.created_at)}
                </div>
                <div className="truncate pr-4" title={item.executed_at || undefined}>
                  {formatDateTime(item.executed_at)}
                </div>
                <div className="truncate pr-4">{formatTaskDuration(item.duration_seconds, item.status)}</div>
                <div className="flex items-center gap-2 min-w-0" title={item.result || undefined}>
                  {item.status === "FAILED" && item.failure_type && (
                    <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10 flex-shrink-0">
                      {failureTypeLabel[item.failure_type] || item.failure_type}
                    </span>
                  )}
                  <span className="truncate">
                    {item.result || "-"}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
        <div>
          共 {total} 条 · 第 {page}/{totalPages} 页
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(Math.max(1, page - 1))}
              disabled={page === 1 || loading}
            >
              {"<"}
            </Button>
            {pageItems.map((item, idx) =>
              typeof item === "string" ? (
                <span key={`ellipsis-${idx}`} className="px-2 text-slate-400">
                  {item}
                </span>
              ) : (
                <Button
                  key={item}
                  variant={item === page ? "default" : "outline"}
                  size="sm"
                  className={cn(
                    "min-w-9",
                    item === page
                      ? "bg-emerald-500 text-white shadow hover:bg-emerald-500"
                      : "bg-white text-slate-700"
                  )}
                  onClick={() => handlePageChange(item)}
                  disabled={loading}
                >
                  {item}
                </Button>
              )
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
              disabled={page === totalPages || loading}
            >
              {">"}
            </Button>
          </div>
          <div className="flex items-center gap-1">
            <Input
              type="number"
              min={1}
              max={totalPages}
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              className="h-9 w-20"
            />
            <Button variant="outline" size="sm" onClick={handlePageJump} disabled={loading}>
              跳转
            </Button>
          </div>
        </div>
      </div>

      {selectedItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={handleCloseModal}
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
                <p className="text-sm text-slate-500">ID: {selectedItem.id ?? "-"}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleCopyReplayCommand}>
                  复制重跑命令
                </Button>
                <Button variant="outline" size="sm" onClick={handleCloseModal}>
                  关闭
                </Button>
              </div>
            </div>

            <div className="grid gap-4 px-6 py-5 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1">
                <div className="text-slate-500">网址</div>
                <div className="break-all font-medium text-slate-800">{selectedItem.url}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">用户名</div>
                <div className="break-all font-medium text-slate-800">{selectedItem.account}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">密码</div>
                <div className="break-all font-medium text-slate-800">{selectedItem.password}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务状态</div>
                <div className="flex items-center gap-2">{renderStatus(selectedItem.status)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务创建时间</div>
                <div className="font-medium">{formatDateTime(selectedItem.created_at)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务执行时间</div>
                <div className="font-medium">{formatDateTime(selectedItem.executed_at)}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务等待时间</div>
                <div className="font-medium">{formatDurationSeconds(getWaitSeconds(selectedItem))}</div>
              </div>
              <div className="space-y-1">
                <div className="text-slate-500">任务时长 (s)</div>
                <div className="font-medium">{formatTaskDuration(selectedItem.duration_seconds, selectedItem.status)}</div>
              </div>
              {selectedItem.llm_usage && (
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="space-y-1 cursor-help">
                        <div className="text-slate-500">Token 使用</div>
                        <div className="font-medium text-blue-600 underline decoration-dashed decoration-slate-300 underline-offset-2">
                          🤖 {formatNumber(selectedItem.llm_usage.total_tokens)}
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
                              {formatNumber(selectedItem.llm_usage.total_input_tokens)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-600">输出 Token</span>
                            <span className="font-mono text-green-600">
                              {formatNumber(selectedItem.llm_usage.total_output_tokens)}
                            </span>
                          </div>
                          <div className="flex justify-between border-t border-sky-200 pt-2">
                            <span className="font-medium text-slate-900">总计</span>
                            <span className="font-mono font-bold text-slate-900">
                              {formatNumber(selectedItem.llm_usage.total_tokens)}
                            </span>
                          </div>
                        </div>

                        {(selectedItem.llm_usage.total_cached_tokens ||
                          selectedItem.llm_usage.total_reasoning_tokens) && (
                          <div className="space-y-2 border-t border-sky-200 pt-2 text-xs">
                            {selectedItem.llm_usage.total_cached_tokens && (
                              <div className="flex justify-between">
                                <span className="text-slate-600">缓存优化</span>
                                <span className="font-mono text-orange-600">
                                  {formatNumber(selectedItem.llm_usage.total_cached_tokens)}
                                </span>
                              </div>
                            )}
                            {selectedItem.llm_usage.total_reasoning_tokens && (
                              <div className="flex justify-between">
                                <span className="text-slate-600">推理 Token</span>
                                <span className="font-mono text-purple-600">
                                  {formatNumber(selectedItem.llm_usage.total_reasoning_tokens)}
                                </span>
                              </div>
                            )}
                          </div>
                        )}

                        <div className="flex justify-between border-t border-sky-200 pt-2 text-xs">
                          <span className="text-slate-600">LLM 调用轮次</span>
                          <span className="font-mono text-cyan-600">
                            {selectedItem.llm_usage.llm_turns} 次
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
                {selectedItem.status === "FAILED" && selectedItem.failure_type && (
                  <span className="inline-flex items-center rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/10">
                    {failureTypeLabel[selectedItem.failure_type] || selectedItem.failure_type}
                  </span>
                )}
              </div>
              <Input
                readOnly
                value={(selectedItem.result ?? "").replace(/\s+/g, " ").trim()}
                placeholder="暂无结果"
                className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm text-slate-800 shadow-inner focus:outline-none"
              />
            </div>

            <div className="px-6 pb-6">
              <div className="mb-2 text-sm font-semibold text-slate-700">任务日志</div>
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="text-sm font-semibold text-slate-800">登录截图</div>
                </div>
                  {artifactsLoading ? (
                    <div className="relative w-full aspect-[16/10] overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                      <div className="absolute inset-0 animate-pulse bg-slate-100/70" />
                      <MediaLoadingOverlay label="加载中..." />
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
                      <MediaLoadingOverlay label="加载中..." />
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
                      <MediaLoadingOverlay label="加载中..." />
                    </div>
                  ) : artifacts?.video_path ? (
                    <button
                      type="button"
                      className="group relative block w-full"
                      onClick={async () => {
                        if (!selectedItem) return;
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
                          selectedItem.id,
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
        </div>
      )}

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
      </div>
    </div>
  );
}

// Export the main component wrapped in Suspense
export function TasksDrawer() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center gap-2 px-4 py-12 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载中...
      </div>
    }>
      <SubscriptionContent />
    </Suspense>
  );
}
