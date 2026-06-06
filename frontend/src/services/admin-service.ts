import { api } from "@/lib/api";
import type { Me, User, CreateUserPayload } from "./types";

export async function listUsers(): Promise<Me[]> {
  const { data } = await api.get<Me[]>("/auth/users");
  return data;
}

export async function listRoles(): Promise<string[]> {
  const { data } = await api.get<string[]>("/auth/roles");
  return data;
}

export async function createUser(payload: CreateUserPayload): Promise<User> {
  const { data } = await api.post<User>("/auth/users", payload);
  return data;
}
