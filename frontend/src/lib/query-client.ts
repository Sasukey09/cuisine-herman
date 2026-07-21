import { QueryCache, QueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { toast } from "sonner";

import { classifyError, isHandledAuthError } from "@/lib/api-error";

/** Retry network/5xx/timeout (transient — cold starts, blips) up to twice; never
 *  retry a 4xx (the request is wrong, retrying won't help). */
function smartRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    if (status && status >= 400 && status < 500) return false; // 4xx: don't retry
  }
  return true;
}

function makeQueryClient() {
  return new QueryClient({
    // A single place that SEES every failed query. Without it, a failed fetch
    // resolves to `data: undefined`, which each screen rendered as "empty" —
    // telling a paying customer their catalog vanished on a mere network blip.
    // Now every query failure is surfaced (toast), and the screens additionally
    // show an ErrorState with a Réessayer button.
    queryCache: new QueryCache({
      onError: (error) => {
        if (typeof window === "undefined") return;
        if (isHandledAuthError(error)) return; // 401 → silent refresh/redirect
        // Offline is covered by the persistent OfflineBanner; don't double up.
        if (typeof navigator !== "undefined" && navigator.onLine === false) return;
        const info = classifyError(error);
        // Stable id: repeated failures replace the toast instead of stacking.
        toast.error(info.title, { id: "query-error", description: info.message });
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: smartRetry,
        // Gentle backoff so a cold start (Render free tier) gets a moment.
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
        refetchOnWindowFocus: false,
        // Refetch when the tab comes back online, so a reconnection clears any
        // stale error automatically.
        refetchOnReconnect: true,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

/** One shared client in the browser, a fresh one per request on the server. */
export function getQueryClient() {
  if (typeof window === "undefined") {
    return makeQueryClient();
  }
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}
