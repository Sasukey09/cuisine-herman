import axios, {
  AxiosError,
  AxiosHeaders,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/stores/auth-store";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// --- attach access token on every request ---------------------------------
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

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post(`${API_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });
    setTokens(data.access_token, data.refresh_token);
    return data.access_token as string;
  } catch {
    logout();
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
    if (!useAuthStore.getState().refreshToken) {
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
