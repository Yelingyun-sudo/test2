"use client";

import { toast } from "sonner";

const AUTH_EXPIRED_TOAST_KEY = "wa_auth_expired_toast";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export function clearLocalAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("account_name");
}

function base64UrlDecode(input: string): string {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((input.length + 3) % 4);
  const decoded = atob(padded);
  try {
    return decodeURIComponent(
      decoded
        .split("")
        .map((ch) => `%${ch.charCodeAt(0).toString(16).padStart(2, "0")}`)
        .join("")
    );
  } catch {
    return decoded;
  }
}

export function isJwtExpired(token: string, skewSeconds = 30): boolean {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return true;
    const payload = JSON.parse(base64UrlDecode(parts[1])) as { exp?: number };
    if (!payload?.exp) return true;
    const nowSeconds = Math.floor(Date.now() / 1000);
    return payload.exp <= nowSeconds + Math.max(0, skewSeconds);
  } catch {
    return true;
  }
}

export function queueAuthExpiredToast(message = "登录已过期，请重新登录") {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(AUTH_EXPIRED_TOAST_KEY, message);
}

export function popAuthExpiredToast(): string | null {
  if (typeof window === "undefined") return null;
  const message = sessionStorage.getItem(AUTH_EXPIRED_TOAST_KEY);
  if (message) sessionStorage.removeItem(AUTH_EXPIRED_TOAST_KEY);
  return message;
}

let authRedirecting = false;

function redirectToLogin(withToast: boolean) {
  if (typeof window === "undefined") return;
  if (authRedirecting) return;
  authRedirecting = true;

  clearLocalAuth();
  if (withToast) queueAuthExpiredToast();

  if (window.location.pathname !== "/") {
    window.location.replace("/");
  } else if (withToast) {
    toast.error("登录已过期，请重新登录");
  }
}

export async function apiFetch(
  path: string,
  init: RequestInit & { auth?: boolean } = {}
): Promise<Response> {
  const { auth = true, ...requestInit } = init;

  const url =
    path.startsWith("http://") || path.startsWith("https://")
      ? path
      : `${API_BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;

  const headers = new Headers(requestInit.headers);

  if (auth) {
    if (typeof window === "undefined") {
      throw new Error("apiFetch(auth=true) must be called in the browser.");
    }

    const token = localStorage.getItem("access_token") ?? "";
    if (!token) {
      redirectToLogin(false);
      throw new Error("Missing access token");
    }

    if (isJwtExpired(token)) {
      redirectToLogin(true);
      throw new Error("Access token expired");
    }

    if (!headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const res = await fetch(url, { ...requestInit, headers });

  if (auth && (res.status === 401 || res.status === 403)) {
    redirectToLogin(true);
    throw new Error(`Unauthorized (${res.status})`);
  }

  return res;
}

