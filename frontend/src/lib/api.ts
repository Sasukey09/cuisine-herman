import axios, {
  AxiosError,
  AxiosHeaders,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/stores/auth-store";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/** Same-origin session endpoints (Next route handlers). They hold the refresh
 *  token in an httpOnly cookie; the browser never sees it. */
export const SESSION_REFRESH_URL = "/api/session/refresh";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// --- attach the in-memory access token on every request -------------------
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers = AxiosHeaders.from(config.headers);
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

// --- transparent refresh on 401 -------------------------------------------
type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let isRefreshing = false;
let waiters: Array<(token: string | null) => void> = [];

function notifyWaiters(token: string | null) {
  waiters.forEach((cb) => cb(token));
  waiters = [];
}

/** Ask our own origin to mint a new access token from the httpOnly refresh
 *  cookie. Returns the new token, or null when the session is gone. */
export async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(SESSION_REFRESH_URL, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) {
      useAuthStore.getState().clear();
      return null;
    }
    const data = (await res.json()) as { access_token?: string };
    const token = data.access_token ?? null;
    useAuthStore.getState().setAccessToken(token);
    return token;
  } catch {
    useAuthStore.getState().clear();
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;

    if (status !== 401 || !original || original._retry) {
      return Promise.reject(error);
    }

    original._retry = true;

    // If a refresh is already running, queue this request until it finishes.
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        waiters.push((token) => {
          if (!token) return reject(error);
          original.headers = AxiosHeaders.from(original.headers);
          original.headers.set("Authorization", `Bearer ${token}`);
          resolve(api(original));
        });
      });
    }

    isRefreshing = true;
    const newToken = await refreshAccessToken();
    isRefreshing = false;
    notifyWaiters(newToken);

    if (!newToken) {
      if (typeof window !== "undefined") window.location.href = "/login";
      return Promise.reject(error);
    }

    original.headers = AxiosHeaders.from(original.headers);
    original.headers.set("Authorization", `Bearer ${newToken}`);
    return api(original);
  },
);
