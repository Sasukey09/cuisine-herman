"use client";

import { useEffect, useState } from "react";
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
 * Client-side route protection. Waits for the persisted store to hydrate
 * (mounted) before deciding, to avoid an SSR redirect flash.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (mounted && !accessToken) {
      router.replace("/login");
    }
  }, [mounted, accessToken, router]);

  if (!mounted || !accessToken) return <FullScreenLoader />;
  return <>{children}</>;
}
