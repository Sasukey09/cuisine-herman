import axios from "axios";
import { api, API_URL } from "@/lib/api";
import type { AuthTokens, Me, RegisterPayload, User } from "./types";

/**
 * OAuth2 password flow: the backend expects x-www-form-urlencoded with
 * `username` + `password` at POST /auth/token. Uses bare axios (no auth header).
 */
export async function login(email: string, password: string): Promise<AuthTokens> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const { data } = await axios.post<AuthTokens>(`${API_URL}/auth/token`, form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>("/auth/register", payload);
  return data;
}

export async function getMe(): Promise<Me> {
  const { data } = await api.get<Me>("/auth/me");
  return data;
}

/** Revoke every token of the current user (all devices), server-side. */
export async function logout(): Promise<void> {
  await api.post("/auth/logout");
}
