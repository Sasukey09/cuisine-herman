"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { getMe, login as loginApi, register as registerApi } from "@/services/auth-service";
import { useAuthStore } from "@/stores/auth-store";
import type { RegisterPayload } from "@/services/types";

/** Loads the current user (and syncs roles into the store). */
export function useMe(enabled = true) {
  const setUser = useAuthStore((s) => s.setUser);
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const me = await getMe();
      setUser(me);
      return me;
    },
    enabled,
  });
}

export function useLogin() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: async (vars: { email: string; password: string }) => {
      const tokens = await loginApi(vars.email, vars.password);
      setTokens(tokens.access_token, tokens.refresh_token ?? "");
      const me = await getMe();
      setUser(me);
      return me;
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (payload: RegisterPayload) => registerApi(payload),
  });
}

export function useLogout() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const queryClient = useQueryClient();

  return () => {
    logout();
    queryClient.clear();
    router.replace("/login");
  };
}
