import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { Me, RegisterPayload, User } from "./types";

/**
 * Logs in through our same-origin session route: it exchanges the credentials
 * server-side and stows the refresh token in an httpOnly cookie, handing back
 * only the short-lived access token (kept in memory). No token ever reaches
 * localStorage.
 */
export async function login(email: string, password: string): Promise<string> {
  const res = await fetch("/api/session/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data?.access_token) {
    const detail = typeof data?.detail === "string" ? data.detail : "Identifiants incorrects";
    throw new Error(detail);
  }
  return data.access_token as string;
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>("/auth/register", payload);
  return data;
}

export async function getMe(): Promise<Me> {
  const { data } = await api.get<Me>("/auth/me");
  return data;
}

/** Revoke every token of the current user (all devices), server-side, and drop
 *  the httpOnly refresh cookie. */
export async function logout(): Promise<void> {
  const token = useAuthStore.getState().accessToken;
  await fetch("/api/session/logout", {
    method: "POST",
    credentials: "include",
    headers: token ? { authorization: `Bearer ${token}` } : undefined,
  });
}

/** Admin-only: set a new password for a user of the organization. */
export async function resetUserPassword(userId: string, password: string): Promise<void> {
  await api.post(`/auth/users/${userId}/reset-password`, { password });
}

/** Self-service recovery, step 1: ask for a reset link. The backend always
 *  answers the same way (no user enumeration), so this never throws on an
 *  unknown address. */
export async function requestPasswordReset(email: string): Promise<void> {
  await api.post("/auth/forgot-password", { email });
}

/** Self-service recovery, step 2: redeem the emailed token and set a new
 *  password. Throws on an invalid/expired token or a weak password (400). */
export async function confirmPasswordReset(token: string, password: string): Promise<void> {
  await api.post("/auth/reset-password", { token, password });
}
