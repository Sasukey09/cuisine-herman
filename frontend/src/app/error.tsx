"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Anything that throws while rendering lands here instead of Next's unstyled
 * crash screen. `reset()` re-renders the segment, so a transient failure (a bad
 * API payload, a network blip) costs a click, not a lost session.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Keep it in the browser console; a real reporter (Sentry) goes here later.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-secondary">
        <AlertTriangle className="h-6 w-6 text-destructive" />
      </div>

      <div className="space-y-1">
        <h1 className="font-serif text-2xl font-semibold">Cette page n&apos;a pas pu s&apos;afficher</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          Un problème technique est survenu. Vos données ne sont pas perdues — réessayez,
          et si cela se reproduit, signalez-le.
        </p>
      </div>

      <div className="flex gap-2">
        <Button onClick={reset}>
          <RotateCw className="h-4 w-4" />
          Réessayer
        </Button>
        <Button variant="outline" onClick={() => (window.location.href = "/dashboard")}>
          Retour au tableau de bord
        </Button>
      </div>

      {error.digest && (
        <p className="font-mono text-xs text-muted-foreground">Référence : {error.digest}</p>
      )}
    </div>
  );
}
