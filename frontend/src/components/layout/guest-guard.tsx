"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "@/stores/auth-store";

/**
 * Inverse of AuthGuard: redirects already-authenticated users away from
 * guest-only pages (login, register, forgot-password) to the dashboard.
 */
export function GuestGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (mounted && accessToken) {
      router.replace("/dashboard");
    }
  }, [mounted, accessToken, router]);

  if (mounted && accessToken) return null;
  return <>{children}</>;
}
