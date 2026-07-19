"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import {
  getMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
} from "@/services/auth-service";
import { refreshAccessToken } from "@/lib/api";
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
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: async (vars: { email: string; password: string }) => {
      const accessToken = await loginApi(vars.email, vars.password);
      setAccessToken(accessToken);
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
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();

  return () => {
    // Revoke server-side first (bumps token_version) and drop the httpOnly
    // refresh cookie. Best-effort: a network failure must never trap the user.
    void logoutApi().catch(() => undefined);

    clear();
    queryClient.clear();
    router.replace("/login");
  };
}

/**
 * Restores a session on app boot. The access token lives only in memory, so a
 * reload starts with none; this asks our origin to mint a fresh one from the
 * httpOnly refresh cookie. Runs once, then flips `bootstrapped` so the guards
 * can decide without a redirect flash.
 */
export function useSessionBootstrap() {
  const setUser = useAuthStore((s) => s.setUser);
  const setBootstrapped = useAuthStore((s) => s.setBootstrapped);
  const bootstrapped = useAuthStore((s) => s.bootstrapped);

  useEffect(() => {
    if (bootstrapped) return;
    let cancelled = false;
    (async () => {
      const token = await refreshAccessToken();
      if (!cancelled && token) {
        try {
          setUser(await getMe());
        } catch {
          // Token minted but /me failed: leave user null; guards still allow in
          // and the next request will surface any real problem.
        }
      }
      if (!cancelled) setBootstrapped(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [bootstrapped, setUser, setBootstrapped]);

  return bootstrapped;
}
