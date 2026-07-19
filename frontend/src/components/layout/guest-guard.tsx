"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "@/stores/auth-store";

/**
 * Inverse of AuthGuard: redirects already-authenticated users away from
 * guest-only pages (login, register, forgot-password) to the dashboard. Waits
 * for the boot-time session restore before deciding.
 */
export function GuestGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const bootstrapped = useAuthStore((s) => s.bootstrapped);
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (bootstrapped && accessToken) {
      router.replace("/dashboard");
    }
  }, [bootstrapped, accessToken, router]);

  if (bootstrapped && accessToken) return null;
  return <>{children}</>;
}
