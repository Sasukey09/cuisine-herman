"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuthStore } from "@/stores/auth-store";

function FullScreenLoader() {
  return (
    <div className="flex h-screen w-full items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

/**
 * Client-side route protection. Waits for the boot-time session restore
 * (`bootstrapped`) before deciding, so a reload — which starts with the
 * in-memory access token empty until the httpOnly refresh cookie is exchanged —
 * doesn't flash a redirect to /login.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const bootstrapped = useAuthStore((s) => s.bootstrapped);
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (bootstrapped && !accessToken) {
      router.replace("/login");
    }
  }, [bootstrapped, accessToken, router]);

  if (!bootstrapped || !accessToken) return <FullScreenLoader />;
  return <>{children}</>;
}
